import os
from os import path
import sys
import random
from copy import copy
import cPickle as pickle

try:
    import configparser
except:
    import ConfigParser as configparser
    
PlayerList = ["Peb","Pandu","Dhota","Fajar","Keni","Gunar","Fainan"]

GAME_SAVE = "risk.dat"


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
    
class RiskBot:
    def __init__(self, player_handle):
        self.puppet = player_handle
        
    def ask_trade(self):
        """return 1 to assign or 3 to trade"""
        if len(self.puppet.cards)>2:
            if random.randint(1,10)>4:
                return 3
            else:
                return 1
        else:
            return 1
        
    def select_tradecards(self,cardset):
        """return list of integer, index of ordered cards"""
        return [i+1 for i,c in enumerate(cardset)]
        
    def get_deployment(self):
        """return territory object and number of deployment"""
        ocregions = copy(self.puppet.territories)
        random.shuffle(ocregions)
        target_deploy = ocregions.pop()
        return target_deploy, random.randint(1, self.puppet.reserve)
        
    def select_action(self, attack_options):
        """return 0 to end turn or 5 to attack"""
        return 5 if len(attack_options)>0 else 0
        
    def select_attack_target(self, attack_target):
        if len(attack_target) > 1:
            return random.randint(1, len(attack_target))
        else: 
            return 1
        
    def select_attack_source(self, attack_source):
        return random.randint(0, len(attack_source)-1)
        
    def determine_attack_force(self, source_region):
        return source_region.max_mobile()
        
    def decide_continue_attack(self, num_wins, num_loss, is_captured):
        return random.randint(0,1)
        
    def decide_maneuver(self):
        return True
        
    def determine_maneuver_source(self, man_source):
        man = copy(man_source)
        random.shuffle(man)
        source = man.pop()
        return source, random.randint(1, source.max_mobile())
        
    def select_maneuver_target(self, man_target):
        """"""
        random.shuffle(man_target)
        return man_target.pop()

class RiskPlayer:
    def __init__(self, name):
        self.name = name
        self.reserve = 0
        self.cards = []
        self.territories = []
        
    def get_target(self,game,min_troop=0):
        #print "get attack target for",self.name,
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
        #print "done"
        return neighbors
        
    def pick_card(self, game):
        self.cards.append(game.pick_card())
        
    def deploy_to(self, region, num_deploy):
        region.troops += num_deploy
        self.reserve -= num_deploy
        
    def __repr__(self):
        return "RiskPlayer(name=%s,num_cards=%d,num_territories=%d)" % (self.name, len(self.cards), len(self.territories))
        
class RiskTerritory:
    def __init__(self, name, num_star):
        self.name = name
        self.owner = None
        self.troops = 0
        self.star = num_star
        self.neighbors = []
        
    def max_mobile(self):
        return self.troops-1
        
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
        queue = [self]
        while len(queue)>0:
            node = queue.pop()
            result.append(node)
            for neighbor in node.neighbors:
                if neighbor.owner==self.owner and neighbor not in result and neighbor not in queue:
                    queue.append(neighbor)
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
        self.bots = {}
        
    def new_bot(self, name):
        player = self.new_player(name)
        self.bots[name] = RiskBot(player)
        return player
        
    def new_player(self, name):
        player = RiskPlayer(name)
        self.add_player(player)
        return player
        
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
        ter_min = len(self.level.territories)/3-2
        if n_terr >= ter_min:
            n_terr -= ter_min
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
            
    def attack(self, player, source, target, numtroop):
        """return pair of value (num_wins, num_loss, is_captured)"""
        num_attack = numtroop
        source.troops -= num_attack
        
        battle_result = compare_roll(dice_roll(max(3, num_attack)),dice_roll(target.troops))
        num_wins,num_loss=0,0
        for fight in battle_result:
            if fight==1:
                num_wins += 1
                target.troops -= 1
                #guard
                if target.troops==0:
                    break
            elif fight==-1:
                num_loss += 1
                num_attack -= 1
        
        if target.troops==0:
            target.capture(player)
            target.troops = num_attack
            is_captured = True
        else:
            source.troops += num_attack
            is_captured = False
        return num_wins, num_loss, is_captured
        
    def do_maneuver(self, player, source, target, num_troops):
        target.troops += num_troops
        source.troops -= num_troops
        
    def is_winning(self, player):
        return len(player.territories) > self.winning_threshold()
        
    def save(self, filename):
        with open(filename, "wb") as game_save:
            pickle.dump(self, game_save)
            
    @staticmethod
    def load(filename):
        with open(filename, "rb") as game_save:
            instance = pickle.load(game_save)
        return instance
        
O_EXIT = "Exit game"
O_CONTINUE = "Continue"
O_SAVE = "Save game"
O_QUIT = "Exit"

class RiskApp:
    def __init__(self):
        self.game = RiskGame()
        
    def menu(self,options, message=None):
        while True:
            if message is None:
                print "Available options : "
            else:
                print message
            for i,item in enumerate(options):
                print i, item
            str_in = raw_input("Please select (0..%d)" % (len(options)-1)).strip()
            if len(str_in)==0 or not str_in.isdigit(): continue
            v = int(str_in)
            if v in range(0,len(options)):
                break
        return v
        
    def menu_multi(self,options, message=None):
        while True:
            if message is None:
                print "Available options : "
            else:
                print message
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
                                
    def all_players_stat(self):
        for player in self.game.turn_order:
            print player.name,"occupied",len(player.territories),"region(s)",
            if len(player.cards)==0:
                print
            else:
                print "and has",len(player.cards),"card(s)"
                                            
    def run(self):
        game = self.game
        all_bot = False
        while not game.is_terminated():
            if game.state == S_START:
                print "RISK GAME"
                print "Select map"
                levels = game.get_levels()
                options = [O_EXIT]
                if path.exists("risk.dat"):
                    options.append(O_CONTINUE)
                
                sel = self.menu(options+levels)
                if sel == 0:
                    game.stop()
                else:
                    if len(options)>1:
                        if sel == 1:
                            self.game = RiskGame.load("risk.dat")
                            game = self.game
                        else:
                            game.load_level(levels[sel-2])
                    else:
                        game.load_level(levels[sel-1])
                    print game.level
            
            elif game.state == S_INIT:
                print "Setup players"
                level = self.game.level
                num_players = self.ask("How many players (%d..%d) ?" % \
                    (level.min_player, level.max_player), level.min_player, level.max_player)
                
                namelist = copy(PlayerList)
                random.shuffle(namelist)
                for i in xrange(0, num_players):
                    name = raw_input("Player %d's name (empty for bot):" % (i+1))
                    if len(name.strip())==0:
                        name = namelist.pop()
                        game.new_bot(name)
                    else:
                        game.new_player(name)
                        
                all_bot = all([player.name in game.bots for player in game.players])
                    
                print "Ordering turn"
                game.order_turn()
                print [p.name for p in game.turn_order]
                
                print "Distributing initial territories"
                game.init_territories()
                print "\t\tSTART"
                game.state = S_TURN
                
            elif game.state == S_TURN:
                player = game.get_turn()
                if len(player.territories)==0: 
                    game.end_turn()
                    continue
                is_bot = player.name in game.bots
                robot = game.bots[player.name]
                print "\t\t",player.name,"turn"
                game.order_territories()
                
                print player.name, "occupied", len(player.territories), "region(s)"
                reserve = 3+game.get_bonus_troops(player)
                player.reserve += reserve
                print player.name, "receives", reserve
                
                if is_bot:
                    sel = robot.ask_trade() #trade or assign
                else:
                    turn_options = ["Quit", "Assign troops","Game overview"]
                    if len(player.cards)>0:
                        turn_options.append("Trade risk card(s)")
                    sel = self.menu(turn_options)
                    
                if sel==0:
                    if self.menu([O_QUIT, O_SAVE])==1:
                        game.save(GAME_SAVE)
                    game.stop()
                
                elif sel==2:
                    self.all_players_stat()
                    
                elif sel==3:
                    ordered_cards = sorted(player.cards, key=lambda c:c.star)
                    if is_bot:
                        sel_opt = robot.select_tradecards(ordered_cards)
                    else:
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
                    while player.reserve > 0:
                        if not all_bot:
                            self.player_stat(player)
                        
                        if is_bot:
                            target_deploy, num_deploy = robot.get_deployment() # > 0
                        else:
                            t_id = self.menu([r.name for r in player.territories])
                            target_deploy = player.territories[t_id]
                            
                            num_deploy = self.ask("How many troops (max. %d)?" % player.reserve, 1, player.reserve)
                            
                        if num_deploy==0:
                            sel_done = self.menu(["Done", "Assign troops"])
                            if sel_done==0:
                                break
                        else:
                            player.deploy_to(target_deploy, num_deploy)
                            print player.name,"deployed", num_deploy,"troop(s) to",target_deploy.name,"total",target_deploy.troops
                        
                    sel = -1
                    capture_win = False
                    while sel != 0:
                        options = ["End Turn","Game overview", "Show borders","Show occupied","Show cards"]
                        attack_ready = player.get_target(self.game,1)
                        if len(attack_ready)>0:
                            options.append("Attack")
                        
                        if is_bot:
                            sel = robot.select_action(attack_ready)
                        else:
                            sel = self.menu(options)
                            
                        if sel==1:
                            self.all_players_stat()
                            
                        elif sel==2:#show border stat
                            self.border_stat(player)
                            
                        elif sel==3:
                            self.player_stat(player)
                                    
                        elif sel==4:#show cards in hand
                            if len(player.cards)==0:
                                print player.name,"has no cards in hand"
                            else:
                                total = 0
                                for card in player.cards:
                                    total += card.star
                                    print card.star
                                print player.name,"has %d stars" % total
                            
                        elif sel==5:#attack
                            attack_target = player.get_target(self.game,1)
                            if is_bot:
                                sel_target = robot.select_attack_target(attack_target)
                            else:
                                print "Select attack target"
                                sel_target = self.menu(["Cancel"]+["%s (%d)" %(r.name,int(r.troops)) for r in attack_target])
                                
                            if sel_target>0:
                                target = attack_target[sel_target-1]
                                
                                attack_source = [region for region in target.neighbors if region.owner==player and region.troops>1]
                                if len(attack_source)>1:
                                    if is_bot:
                                        sel_source = robot.select_attack_source(attack_source)
                                    else:
                                        print "Select attack source"
                                        sel_source = self.menu(["%s (%d)" % (r.name, r.troops) for r in attack_source])
                                        
                                    source = attack_source[sel_source]
                                else:
                                    source = attack_source[0]
                                
                                is_captured = False
                                continue_attack = True
                                while continue_attack:
                                    if is_bot:
                                        num_attack = robot.determine_attack_force(source)
                                    else:
                                        num_attack = self.ask("How many troops deployed (max %d)?" % (source.troops-1), 1, source.troops-1)
                                        
                                    print player.name,"attacked",target.name,"using",num_attack,"force"
                                    
                                    before_battle = copy(target)
                                    
                                    num_wins,num_loss,is_captured = game.attack(player, source, target, num_attack)
                                    
                                    if num_wins > 0:
                                        print player.name,"defeated",num_wins,"enemy force"
                                    if num_loss > 0:
                                        print player.name,"lost",num_loss,"force(s)"
                                    if num_loss==0 and num_wins==0:
                                        print "the battle is draw"
                                        
                                    if target.troops<0:
                                        print "ERROR: ",target.name,"troops is",target.troops
                                        print "before battle: ",target.troops," battle info win:",num_wins,"loss:",num_loss
                                        sys.exit(1)
                                    if not is_captured:
                                        print target.name,"still guarded by",target.troops,"force"
                                    
                                    continue_attack = num_attack>num_loss and not is_captured
                                    if continue_attack:
                                        if is_bot:
                                            continue_attack = robot.decide_continue_attack(num_wins, num_loss,is_captured)
                                        else:
                                            continue_attack = self.menu(["Cease fire","Continue attack"])==1
                                        
                                if is_captured:
                                    capture_win = True
                                    print player.name,"conquered",target.name
                                    print target.name,"occupied by",target.troops
                                    print player.name,"now has",len(player.territories),"region(s)"
                                    
                                    if game.is_winning(player):
                                        print player.name,"WINS"
                                        game.stop()
                                        break
                    
                    #End turn
                    if game.is_winning(player):
                        self.all_players_stat()
                        break
                    else:
                        if capture_win:
                            print player.name,"pick a card from the deck"
                            player.pick_card(game)
                                    
                        maneuver_source = [r for r in player.territories if r.max_mobile()>0]
                        if len(maneuver_source)>0:
                            if (is_bot and robot.decide_maneuver()) or self.menu(["End turn","Maneuver"])==1:
                                while True:
                                    
                                    if is_bot:
                                        source, num_man = robot.determine_maneuver_source(maneuver_source)
                                    else:
                                        sel_source = self.menu(["%s (%d)" % (r.name, r.troops) for r in maneuver_source])
                                        source = maneuver_source[sel_source]
                                    
                                        num_man = self.ask("How many troop(s)? (max %d)" % (source.max_mobile()), 0, source.max_mobile())
                                    
                                    if num_man > 0:
                                        available_target = source.get_accessible_nodes()
                                    
                                        if is_bot:
                                            target = robot.select_maneuver_target(available_target)
                                        else:
                                            sel_target = self.menu([r.name for r in available_target])
                                            target = available_target[sel_target]
                                    
                                        game.do_maneuver(player, source, target, num_man)
                                        print player.name,"moved",num_man,"troops from",source.name,"to",target.name
                                        break
                        game.end_turn()
            else:
                break

def main(argv=sys.argv):
    RiskApp().run()
    #print compare_roll(dice_roll(3), dice_roll(2))
    
if __name__ == "__main__":
    main()