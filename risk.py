import os
from os import path
import sys
import random
from copy import copy

try:
    import configparser
except:
    import ConfigParser as configparser
    
PlayerList = ["Peb","Pandu","Dhota","Fajar","Keni","Gunnar","Fainan"]


def dice_roll(num=1):
    result = []
    for roll_step in xrange(0, num):
        result.append(random.randint(1,6))
    if len(result)==1:
        return result
    else:
        return sorted(result, reverse=True)
    
def compare_roll(attack, defense):
    n_comp = min(len(attack), len(defense))
    result = []
    # 0 : draw
    # 1 : attacker wins
    # -1 : defender wins
    for i in xrange(0, n_comp):
        if attack[i]==defense[i]:
            result.append(0)
        elif attack[i]>defense[i]:
            result.append(1)
        else:
            result.append(-1)
    return result

class RiskPlayer:
    def __init__(self, name):
        self.name = name
        self.reserve = 0
        self.cards = []
        self.territories = []
        
    def get_target(self,game,min_troop=0):
        neighbors = []
        for group in game.level.groups:
            group_neighbors = []
            for region in group.regions:
                if region.owner==self:
                    if region.troops>min_troop:
                        for neighbor in region.neighbors:
                            if neighbor.owner != self and neighbor not in group_neighbors+neighbors:
                                group_neighbors.append(neighbor)
            if len(group_neighbors)>0:
                neighbors += sorted(group_neighbors, reverse=True, key=lambda x:x.troops)
        return neighbors
        
    def __repr__(self):
        return "RiskPlayer(name=%s,num_cards=%d,num_territories=%d)" % (self.name, len(self.cards), len(self.territories))
        
class RiskTerritory:
    def __init__(self, name, num_star):
        self.name = name
        self.owner = None
        self.troops = 0
        self.star = num_star
        self.neighbors = []
        
    def assign(self,player):
        self.owner = player
        player.territories.append(self)
        self.troops = self.star
        print player.name, "acquired", self.name
        
    def occupy(self,player):
        self.owner = player
        self.owner.territories.append(self)
        
    def capture(self,player):
        self.owner.territories.remove(self)
        self.occupy(player)
        
    def add_neighbor(self,territory):
        if territory not in self.neighbors:
            self.neighbors.append(territory)
            if self not in territory.neighbors:
                territory.neighbors.append(self)
                
    def get_accessible_nodes(self,ref=[]):
        result = []
        for r in self.neighbors:
            if r.owner == self.owner and r not in result+ref:
                result.append(r)
        for r in result:
            result += r.get_accessible_nodes(result+ref)
        return result
                
    def neighbor_analysis(self):
        result = []
        neighbormap = {}
        for neighbor in self.neighbors:
            neighbormap[neighbor.name] = neighbor.troops
        result = sorted(neighbormap.items(), key=lambda x: x[1])
        return result
                
    def __repr__(self):
        if self.owner is None:
            return "RiskTerritory(name=%s,num_troops=%d)" % (self.name, self.troops)
        return "RiskTerritory(name=%s,owner=%s,num_troops=%d)" % (self.name, repr(self.owner.name), self.troops)
                
class RiskTerritoryGroup:
    def __init__(self, name, bonus):
        self.name = name
        self.bonus = bonus
        self.regions = []
        
    def add_region(self,region):
        self.regions.append(region)
                
class RiskLevel:
    def __init__(self):
        self.name = ""
        self.groups = []
        self.territories = []
        self.min_player = 0
        self.max_player=0
        
    def load(self,filename):
        lvl = configparser.ConfigParser()
        lvl.readfp(open(filename))
        self.name = lvl.get('level','name')
        self.min_player = lvl.getint('rule','min_players')
        self.max_player = lvl.getint('rule','max_players')
        self.min_territories=[int(v) for v in lvl.get('rule','min_territories').split(',')]
        self.min_trade=lvl.getint('traderule','min_trade')
        self.max_trade=lvl.getint('traderule','max_trade')
        self.trade_count=[int(v) for v in lvl.get('traderule','trade_num').split(',')]
        groups = [grp.strip() for grp in lvl.get('level','groups').split(",")]
        regionmap = {}
        for group in groups:
            g_name = lvl.get(group,'name')
            g_bonus = lvl.getint(group,'bonus_troop')
            g_areas = [reg.strip() for reg in lvl.get(group,'regions').split(',')]
            risk_group = RiskTerritoryGroup(g_name, g_bonus)
            self.groups.append(risk_group)
            for region in g_areas:
                r_name = lvl.get(region,'name')
                r_star = lvl.getint(region,'num_star')
                risk_region = RiskTerritory(r_name, r_star)
                regionmap[region] = risk_region
                risk_group.add_region(risk_region)
                
        for region in regionmap:
            self.territories.append(regionmap[region])
            
        connection_start = False
        with open(filename) as f:
            for line in f:
                if not connection_start: 
                    if "[connection]" == line.strip():
                        connection_start = True
                    continue
                #print line
                r1,r2 = tuple([item.strip() for item in line.strip().split("=")])
                regionmap[r1].add_neighbor(regionmap[r2])
        
    def save(self, filename):
        pass
        
    def __repr__(self):
        return "RiskLevel(name=%s,num_groups=%d,num_territories=%d)" % (self.name,len(self.groups), len(self.territories))
        

S_START = 0
S_INIT = 1
S_STOP = 2
S_TURN = 3
S_BATTLE = 4

class RiskGame:
    def __init__(self):
        self.level = None
        self.players = []
        self.state = S_START#start,stop,level_select,turn,battle
        self.turn_order = []
        self.turn = -1
        self.active = None
        self.leveldir = "levels"
        self.num_turn = 0
        self.deck = []
        
    def get_levels(self):
        return [dir for dir in os.listdir(self.leveldir) if path.isdir(path.join(self.leveldir, dir))]
        
    def load_level(self, level):
        self.level = RiskLevel()
        self.level.load(path.join(self.leveldir,level,"map.cfg"))
        self.state = S_INIT
        self.deck = copy(self.level.territories)
        random.shuffle(self.deck)
        
    def is_terminated(self):
        return self.state == S_STOP
        
    def stop(self):
        self.state = S_STOP
        
    def pick_card(self):
        return self.deck.pop()
        
    def add_player(self, player):
        self.players.append(player)
        
    def order_turn(self):
        num_player = len(self.players)
        playermap = {}
        player_roll = {}
        for p in self.players:
            playermap[p.name] = p
            player_roll[p.name] = dice_roll()[0]
        ordering = sorted(player_roll.items(), reverse=True, key=lambda x:x[1])
        self.turn_order = [playermap[p_name] for p_name, roll in ordering]
        self.turn = 0
        
    def order_territories(self):
        for p in self.players:
            p_terr = []
            for g in self.level.groups:
                for r in g.regions:
                    if r.owner==p:
                        p_terr.append(r)
            p.territories = p_terr
        
    def get_turn(self):
        return self.turn_order[self.turn]
        
    def end_turn(self):
        self.turn += 1
        self.turn %= len(self.players)
        
    def winning_threshold(self):
        return self.level.min_territories[len(self.players)-self.level.min_player]
        
    def init_territories(self):
        terr_list = copy(self.level.territories)
        random.shuffle(terr_list)
        turn = 0
        while len(terr_list)>0:
            item = terr_list.pop()
            if len(terr_list)<len(self.players):
                item.assign(self.turn_order[(len(self.players)-turn-1)%len(self.players)])
            else:
                item.assign(self.turn_order[turn%len(self.players)])
            turn += 1
            turn %= len(self.players)
        #order player's territories by group/continent
        self.order_territories()
            
    def get_bonus_troops(self, player):
        bonus = 0
        n_terr = len(player.territories)
        if n_terr > 11:
            n_terr -= 12
            t_bonus = 1+n_terr/3
            bonus += t_bonus
            #print "territory bonus", t_bonus,
            
        g_bonus = 0
        for group in self.level.groups:
            own_group = True
            for region in group.regions:
                if region.owner != player:
                    own_group = False
                    break
            if own_group:
                g_bonus += group.bonus
                bonus += g_bonus
        #if g_bonus>0: print "Region group bonus", g_bonus,
        return bonus
        
    def trade_cards(self, player, cards_list):
        n_stars = 0
        for card in cards_list:
            n_stars += card.star
        if n_stars < self.level.min_trade or n_stars > self.level.max_trade:
            return False
        else:
            player.reserve += self.level.trade_count[n_stars-self.level.min_trade]
            return True
            
        
O_EXIT = "Exit game"

class RiskApp:
    def __init__(self):
        self.game = RiskGame()
        
    def menu(self,options):
        while True:
            print "Available options : "
            for i,item in enumerate(options):
                print i, item
            str_in = raw_input("Please select (0..%d)" % (len(options)-1)).strip()
            if len(str_in)==0 or not str_in.isdigit(): continue
            v = int(str_in)
            if v in range(0,len(options)):
                break
        return v
        
    def menu_multi(self,options):
        while True:
            print "Available options : "
            print 0,"Cancel"
            for i,item in enumerate(options):
                print i+1, item
            str_in = raw_input("Please select one above or comma separated options (1..%d)" % (len(options))).strip()
            if len(str_in)==0: continue
            if str_in.isdigit():
                v = int(str_in)
                if v in range(0,len(options)+1):
                    v = [v]
                    break
            else:
                if str_in.index(",") != -1:
                    v = [int(vs.strip()) for vs in str_in.split(",") if int(vs.strip()) in range(1,len(options)+1)]
            
        return v
        
    def ask(self, question, low, high):
        while True:
            str_in = raw_input(question)
            if len(str_in)==0 or not str_in.isdigit(): continue
            v = int(str_in)
            if v >= low and v <= high:
                break
        return v
        
    def border_stat(self,player):
        borders = player.get_target(self.game)
        for region in borders:
            print region.name,"owned by",region.owner.name
            for r in region.neighbors:
                if r.owner != player: 
                    if r.owner==region.owner:
                        print "  ",region.name,"is backed by",r.name,"with",r.troops,"force"
                    else:
                        print "  ",r.owner.name,"occupied",r.name,"with",r.troops,"force"
        
    def player_stat(self,player):
        for group in self.game.level.groups:
            for region in group.regions:
                if region.owner==player:
                    print region.name,"has",region.troops
                    for r in region.neighbors:
                        if r.owner != player: 
                            if r.owner==player:
                                print "  ",region.name,"is backed by",r.name,"with",r.troops,"force"
                            else:
                                print "  ",r.owner.name,"occupied",r.name,"with",r.troops,"force"
                                            
    def run(self):
        game = self.game
        while not game.is_terminated():
            if game.state == S_START:
                print "RISK GAME"
                print "Select map"
                levels = game.get_levels()
                sel = self.menu([O_EXIT]+levels)
                if sel == 0:
                    game.stop()
                else:
                    game.load_level(levels[sel-1])
                    print game.level
            
            elif game.state == S_INIT:
                print "Setup players"
                num_players = self.ask("How many players (3..5) ?", 3, 5)
                
                namelist = copy(PlayerList)
                random.shuffle(namelist)
                for i in xrange(0, num_players):
                    #name = raw_input("Player %d's name :" % (i+1))
                    #comment line below and uncomment line above for manual input
                    name = namelist.pop()
                    player = RiskPlayer(name)
                    game.add_player(player)
                    
                print "Ordering turn"
                game.order_turn()
                print [p.name for p in game.turn_order]
                
                print "Distributing initial territories"
                game.init_territories()
                print "\t\tSTART"
                game.state = S_TURN
                
            elif game.state == S_TURN:
                player = game.get_turn()
                print "\t\t",player.name,"turn"
                game.order_territories()
                
                print player.name, "occupied", len(player.territories), "region(s)"
                reserve = 3+game.get_bonus_troops(player)
                player.reserve += reserve
                print player.name, "receives", reserve
                
                turn_options = ["Quit", "Assign troops"]
                if len(player.cards)>0:
                    turn_options.append("Trade risk card(s)")
                sel = self.menu(turn_options)
                if sel==0:
                    game.stop()
                
                elif sel==2:
                    ordered_cards = sorted(player.cards, key=lambda c:c.star)
                    sel_opt = self.menu_multi(["%s (%d)" % (card.name, card.star) for card in ordered_cards])
                    cards_to_trade = []
                    if len(sel_opt)==1 and sel_opt[0]==0:
                            continue
                    else:
                        for sel_o in sel_opt:
                            sel_card = ordered_cards[sel_o-1]
                            cards_to_trade.append(sel_card)
                            player.cards.remove(sel_card)
                        if not game.trade_cards(player, cards_to_trade):
                            #put cards back to player
                            for card in cards_to_trade:
                                player.cards.append(card)
                        else:
                            print player.name, "trade risk %d card to receive" % (len(cards_to_trade)), player.reserve
                
                elif sel==1:
                    print "Assign troops"
                    while reserve > 0:
                        self.player_stat(player)
                        
                        t_id = self.menu([r.name for r in player.territories])
                        num_deploy = self.ask("How many troops (max. %d)?" % reserve, 1, reserve)
                        target_deploy = player.territories[t_id]
                        target_deploy.troops += num_deploy
                        reserve -= num_deploy
                        print player.name,"deployed", num_deploy,"troop(s) to",target_deploy.name,"total",target_deploy.troops
                        
                    sel = -1
                    capture_win = False
                    while sel != 0:
                        options = ["End Turn","Show borders","Show occupied","Show cards"]
                        attack_ready = player.get_target(self.game,1)
                        if len(attack_ready)>0:
                            options.append("Attack")
                        
                        sel = self.menu(options)
                        if sel==1:#show border stat
                            self.border_stat(player)
                            
                        elif sel==2:
                            self.player_stat(player)
                                    
                        elif sel==3:#show occupied stat
                            if len(player.cards)==0:
                                print player.name,"has no cards in hand"
                            else:
                                total = 0
                                for card in player.cards:
                                    total += card.star
                                    print card.star
                                print player.name,"has %d cards" % total
                            
                        elif sel==4:#attack
                            attack_target = player.get_target(self.game,1)
                            print "Select attack target"
                            sel_target = self.menu(["Cancel"]+["%s (%d)" %(r.name,int(r.troops)) for r in attack_target])
                            if sel_target>0:
                                target = attack_target[sel_target-1]
                                
                                attack_source = [region for region in target.neighbors if region.owner==player and region.troops>1]
                                if len(attack_source)>1:
                                    print "Select attack source"
                                    sel_source = self.menu(["%s (%d)" % (r.name, r.troops) for r in attack_source])
                                    source = attack_source[sel_source]
                                else:
                                    source = attack_source[0]
                                num_attack = 0
                                continue_attack = True
                                while continue_attack:
                                    if num_attack>0:
                                        source.troops += num_attack
                                    num_attack = self.ask("How many troops deployed (max %d)?" % (source.troops-1), 1, source.troops-1)
                                    print player.name,"attacked",target_deploy.name,"using",num_attack,"force"
                                    source.troops -= num_attack
                                    
                                    battle_result = compare_roll(dice_roll(max(3, num_attack)),dice_roll(target.troops))
                                    num_wins,num_loss=0,0
                                    for fight in battle_result:
                                        if fight==1:
                                            num_wins += 1
                                            target.troops -= 1
                                        elif fight==-1:
                                            num_loss += 1
                                            num_attack -= 1
                                    if num_wins > 0:
                                        print player.name,"defeated",num_wins,"enemy force"
                                    if num_loss > 0:
                                        print player.name,"lost",num_loss,"force(s)"
                                    if num_loss==0 and num_wins==0:
                                        print "the battle is draw"
                                    if target.troops>0:
                                        print target.name,"still guarded by",target.troops,"force"
                                    
                                    continue_attack = num_attack>0 and target.troops>0
                                    if continue_attack:
                                        continue_attack = self.menu(["Cease fire","Continue attack"])==1
                                        
                                if target.troops==0:
                                    target.capture(player)
                                    target.troops = num_attack
                                    capture_win = True
                                    print player.name,"conquered",target.name
                                    print target.name,"occupied by",target.troops
                                    print player.name,"now has",len(player.territories),"region(s)"
                                    if(len(player.territories)>game.winning_threshold()):
                                        print player.name,"WINS"
                                        game.stop()
                                        break
                    
                    #End turn
                    if capture_win:
                        print player.name,"pick a card from the deck"
                        player.cards.append(game.pick_card())
                                
                    maneuver_source = [r for r in player.territories if r.troops>1]
                    if len(maneuver_source)>0:
                        sel = self.menu(["End turn","Maneuver"])
                        if sel==1:
                            sel_source = self.menu([r.name for r in maneuver_source])
                            source = maneuver_source[sel_source]
                            max_man = source.troops-1
                            num_man = self.ask("How many troop(s)? (max %d)" % (max_man), 1, max_man)
                            available_target = source.get_accessible_nodes()
                            sel_target = self.menu([r.name for r in available_target])
                            target = available_target[sel_target]
                            target.troops += num_man
                            source.troops -= num_man
                            print player.name,"moved",num_man,"troops from",source.name,"to",target.name
                    game.end_turn()
            else:
                break

                
        
def main(argv=sys.argv):
    RiskApp().run()
    #print compare_roll(dice_roll(3), dice_roll(2))
    
if __name__ == "__main__":
    main()