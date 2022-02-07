# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals, division

from dataclasses import dataclass
from collections import defaultdict
from enum import Enum

class SupplyType(Enum):
    WORKER = 1
    ARMY = 2
    CAPACITY = 3

@dataclass
class UnitSupply:
    """ Data structure to hold information about a single unit's supply."""
    build_time: int
    supply: float
    supply_type: SupplyType = SupplyType.ARMY      

class ActivePlayerSupply:
    def __init__(self):
        self.preproduction = {}
        self.production = {}
        self.units = {}
        self.structures = {}
        
    def get_current_supply(self):
        workers = 0
        army = 0
        capacity = 0
        #for uid,unit_supply in active_units.:
        
class PlayerSupply:
    """ Data structure to hold supply information. """
    
    def __init__(self):
        """ Create a new _Supply instance. """
        self.data = [(0,0,0,0)] # list of tuples [(time,workers,army,capacity)]
        self.production = [(0,{})] # 
        self.units = [(0,{})] # 
        self.structures = [(0,{})] # 
        #self.supply_capped_real_seconds = 0

    def add(self,event_time,workers=0,army=0,capacity=0):
        latest_supply = self.data[-1][1:]
        new_supply = tuple(map(lambda x,y:x+y, latest_supply,(workers,army,capacity)))
        self.data.append( (event_time,)+new_supply )
        
    def sync(self,frame,cursup):
        if not isinstance(cursup,ActivePlayerSupply):
            tb = sys.exc_info()[2]
            errmsg = 'PlayerSupply.sync() expects argument of type ActivePlayerSupply.'
            raise TypeError(errmsg).with_traceback(tb)
#         print('k we got here')
        for attr in ['production','units','structures']:
#             print(f'  attr is {attr}')
            current = cursup.__getattribute__(attr)
            record = self.__getattribute__(attr)
            d = {}
#             print(f'current is {current}')
#             print(current.values())
#             print('  goin into loop')
            for unit in current.values():
#                 print(f'    unit is {unit}')
                key = (unit.name,unit)
                d[key] = d.get(key,0)+1
#             print(' finished looping over current vals')
            if (record[-1][0]==frame):
                record.pop()
                record.append((frame,d))
            elif (record[-1][1] != d):
                record.append((frame,d))
        # loop over record to sum up supply

    @staticmethod
    def _timestr_to_seconds(timestr,useGameTimeStr=True):
        m,s = map(int,timestr.split(':'))
        s += m*60
        if useGameTimeStr:
            s = s*1.4
        return s
        
    @staticmethod
    def _seconds_to_timestr(seconds,useGameTimeStr=True):
            s = seconds
            if useGameTimeStr:
                s = s/1.4
            m = s/60.0
            return f'{int(m)}:{int((m-int(m))*60.0):02}'

    def time_supply_capped(self,useGameTime=True):
        return self._seconds_to_timestr(self.supply_capped_real_seconds,useGameTime)    
    
    def workers(self):
        return [(d[0],d[1]) for d in self.data]
    
    def army(self):
        return [(d[0],d[2]) for d in self.data]
    
    def supply(self):
        return [(d[0],d[1]+d[2]) for d in self.data]
    
    def capacity(self):
        return [(d[0],d[3]) for d in self.data]    
    
    
class SupplyTracker(object):

    name = "SupplyTracker"

    def unwrapUnitEvent(self,event):
        try:
            frame = event.frame
            unit = event.unit._type_class
            uid = event.unit_id
            if event.unit.owner:
                pid = event.unit.owner.pid
                acs = self.active_supply[pid]
            else:
                pid = None
                acs = None
            return (frame,unit,uid,pid,acs)
        except:
            print(f'Unhandled UnitEvent {event}.')
            raise
                
    def handleInitGame(self, event, replay):
        try:
            ## This dictionary contains the supply of every unit
            self.supply_units = self.getUnitSupplyData()
            self.supply = dict()                 
            self.active_supply = dict()

            for player in replay.players:
                self.supply[player.pid] = PlayerSupply()
                self.active_supply[player.pid] = ActivePlayerSupply()

            ## This list contains a tuple of the units supply and unit ID.
            ## the purpose of the list is to know which user owns which unit
            ## so that when a unit dies, that
            self.units_alive = dict()
            ##
            self.supply_gen = dict()

            for player in replay.players:
                self.supply_gen[player.pid] = list()
                self.units_alive[player.pid] = list()
                #player.supply = PlayerSupply()
                player.current_food_used = defaultdict(int)
                player.current_food_made = defaultdict(int)
                player.time_supply_capped = int()
        except:
            print('Error in SupplyTracker handleInitGame(...)')

    def handleUnitTypeChangeEvent(self,event,replay):
        try:
            f,unit,uid,pid,acs = self.unwrapUnitEvent(event)
            if event.unit_type_name=="Egg":
                # spend larva from units and put egg in preprod queue
                # where it waits for a corresponding "Morph" event
                acs.units.pop(uid)
                acs.preproduction.setdefault(f,[]).append(uid)
            elif event.unit_type_name=="Larva":
                # remove egg from production and add larva back to units
                acs.production.pop(uid, None) # this shouldn't need to be none probably, diagnose
                acs.units[uid]=unit
            # are there more UnitTypeChangeEvents for other unit morphs (lurker,broods)?
            self.supply[pid].sync(f,acs)
        except:
            print(f'Unhandled UnitTypeChangeEvent : {event}')
        
    def handleBasicCommandEvent(self, event, replay):
        try:
            f = event.frame
            pid = event.player.pid
            if event.has_ability:
                acs = self.active_supply[pid]
                if event.ability.name.startswith('MorphTo'):
                    pass # handle ravagers, lurkers, broods, banes, ovies
                elif event.ability.name.startswith('Morph'):
                    unit = event.ability.build_unit
                    preprod = acs.preproduction
                    larva_id = acs.preproduction[f].pop(0)
                    if not acs.preproduction[f]:
                        acs.preproduction.pop(f)
                    acs.production[larva_id]=unit
                self.supply[pid].sync(f,acs)
            # may need to handle Terran and Protoss events here as well
        except:
            print(f'Unhandled BasicCommandEvent : {event}')
                  
            
    def handleUnitInitEvent(self, event, replay):
        try:
            f,unit,uid,pid,acs = self.unwrapUnitEvent(event)
            acs.production[uid]=unit
            self.supply[pid].sync(f,acs)
        except:
            print(f'Unhandled UnitInitEvent : {event}')
        
    def handleUnitDoneEvent(self, event, replay):
        try:
            f,unit,uid,pid,acs = self.unwrapUnitEvent(event)
            acs.production.pop(uid)
            acs.structures[uid] = unit
            self.supply[pid].sync(f,acs)
        except:
            print(f'Unhandled UnitDoneEvent : {event}')

    def handleUnitBornEvent(self, event, replay):
        try:
            f,unit,uid,pid,acs = self.unwrapUnitEvent(event)
            if pid:
                if not unit.name.startswith('Beacon'):
                    if unit.is_building:
                        acs.structures[uid]=unit
                    else:
                        acs.units[uid] = unit
                    self.supply[pid].sync(f,acs)
        except:
            print(f'Unhandled UnitBornEvent : {event}')
            
    def handleUnitDiedEvent(self, event, replay):
        try:
            f,unit,uid,pid,acs = self.unwrapUnitEvent(event)
            if pid:
                if not unit.name.startswith('Beacon'):
                    acs.units.pop(uid,None)
                    acs.production.pop(uid,None)
                    acs.structures.pop(uid,None)
                    self.supply[pid].sync(f,acs)
        except:
            print(f'Unhandled UnitDiedEvent : {event}')

    def handleEndGame(self, event, replay):
        for player in replay.players:
            player.foo = 'bar'
            # need to do any sorting?
            player.supply = self.supply[player.pid]
            player.current_food_used = dict(sorted(player.current_food_used.items()))
            player.current_food_made = dict(sorted(player.current_food_made.items()))
            #player.supply.data.sort(key=lambda x: x[0])
        print('end of game!')
            
    def getUnitSupplyData(self):
        return {
            ### Zerg ### For the swarm!
            "Drone": UnitSupply(17, 1, SupplyType.WORKER),
            "Zergling": UnitSupply(25, 0.5, 25),
            "Baneling": UnitSupply(20, 0),
            "Queen": UnitSupply(50, 2),
            "Hydralisk": UnitSupply(33, 2),
            "Roach": UnitSupply(27, 2),
            "Infestor": UnitSupply(50, 2),
            "Mutalisk": UnitSupply(33, 2),
            "Corruptor": UnitSupply(40, 2),
            "Ultralisk": UnitSupply(55, 6),
            "Broodlord": UnitSupply(34, 2),
            "SwarmHost": UnitSupply(40, 3),
            "Viper": UnitSupply(40, 3),
            "Overlord": UnitSupply(0, 8, SupplyType.CAPACITY),
            "Hatchery": UnitSupply(100, 6, SupplyType.CAPACITY),
            # Terran
            "SCV": UnitSupply(17, 1, SupplyType.WORKER),
            "Marine": UnitSupply(25, 1),
            "Marauder": UnitSupply(30, 2),
            "SiegeTank": UnitSupply(45, 2),
            "Reaper": UnitSupply(45, 1),
            "Ghost": UnitSupply(40, 2),
            "Hellion": UnitSupply(30, 2),
            "Thor": UnitSupply(60, 6),
            "Viking": UnitSupply(42, 2),
            "Medivac": UnitSupply(42, 2),
            "Raven": UnitSupply(60, 2),
            "Banshee": UnitSupply(60, 3),
            "Battlecruiser": UnitSupply(90, 6),
            "BattleHellion": UnitSupply(30, 2),
            "WidowMine": UnitSupply(40, 2),
            "SupplyDepot": UnitSupply(30, 8, SupplyType.CAPACITY),
            "CommandCenter": UnitSupply(100, 15, SupplyType.CAPACITY),
            # Protoss
            "Probe": UnitSupply(17, 1, SupplyType.WORKER),
            "Zealot": UnitSupply(38, 2),
            "Stalker": UnitSupply(42, 2),
            "Sentry": UnitSupply(42, 2),
            "Observer": UnitSupply(30, 1),
            "Immortal": UnitSupply(55, 4),
            "WarpPrism": UnitSupply(50, 2),
            "Colossus": UnitSupply(75, 6),
            "Phoenix": UnitSupply(35, 2),
            "VoidRay": UnitSupply(60, 4),
            "HighTemplar": UnitSupply(55, 2),
            "DarkTemplar": UnitSupply(55, 2),
            "Archon": UnitSupply(12, 4),
            "Carrier": UnitSupply(120, 6),
            "Mothership": UnitSupply(100, 6),
            "MothershipCore": UnitSupply(30, 2),
            "Oracle": UnitSupply(50, 3),
            "Tempest": UnitSupply(60, 4),
            "Pylon": UnitSupply(25, 8, SupplyType.CAPACITY),
            "Nexus": UnitSupply(100, 15, SupplyType.CAPACITY)
        }