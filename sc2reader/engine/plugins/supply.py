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

class TimeSeries(list):
    def try_update(self,new_frame,new_entry):
        try:
            # if new_frame is same as last frame, this supersedes it, so pop last
            if (self and self[-1][0]==new_frame):
                self.pop()
            # only update if new_entry has changed since last entry
            if (not self or self[-1][1]!=new_entry):
                self.append((new_frame,new_entry))
        except:
            print(f'Something went wrong in {self}.try_update().')
            raise
            
    def at_time(self,time):
        i=-1
        for item in self:
            if time < item[0]:
                return self[max(i,0)]
            i += 1

class SupplyTuple(tuple):
    def workers(self):
        return self[0]
    def army(self):
        return self[1]
    def supply(self):
        return self[0]+self[1]
    def capacity(self):
        return self[2]
    
# This is just a TimeSeries object that can filter the data 
# entry using any of the methods defined for SupplyTuple
class SupplyTimeSeries(TimeSeries):
    pass

for fname in dir(SupplyTuple): 
    if fname not in dir(tuple) and not fname.startswith('__'):
        setattr(SupplyTimeSeries, 
                fname, 
                lambda self: TimeSeries([(f,SupplyTuple.__dict__[fname](d)) for f,d in self]))
    
class PlayerSupply:
    """ Data structure to hold supply information. """
    
    def __init__(self):
        """ Create a new _Supply instance. """
        self.data = SupplyTimeSeries([(0,SupplyTuple((0,0,0)))]) # list of tuples [(frame,(workers,army,capacity))]
        self.production = SupplyTimeSeries([(0,{})]) # (frame, production queue at frame)
        self.units = SupplyTimeSeries([(0,{})]) # (frame, units queue at frame)
        self.structures = SupplyTimeSeries([(0,{})]) # (frame, structures queue at frame)
        self.unit_types = {}
        self._supply_capacity = {
            "Overlord":8,
            "Hatchery":6,
            "SupplyDepot":8,
            "CommandCenter":15,
            "Pylon":8,
            "Nexus":15,
        }
        #self.supply_capped_real_seconds = 0
        

    def count_supply(self):
#         print('I will count up supply from all the queues...')
        try:
            w = 0 # workers
            a = 0 # army
            c = 0 # capacity
            for attr in ['production','units','structures']:
                queue = self.__getattribute__(attr)[-1][1]
                for uname,cnt in queue.items():
                    u = self.unit_types[uname]
                    w += cnt*u.supply*u.is_worker
                    a += cnt*u.supply*u.is_army
                    if (attr!='production'):
                        c += cnt*self._supply_capacity.get(uname,0)
                    elif (uname=='Zergling'):  # zerglings in production queue; 2 per egg
                        a += cnt*u.supply*u.is_army
            w = int(w)
            a = int(a+.6)
            c = int(min(c,200))
            return SupplyTuple((w,a,c))
        except:
            print('something went wrong with count_supply')
    
    @staticmethod
    def built_from_drone(unit):
        try:
            return unit.is_building*(unit.race=='Zerg')*(unit.name not in ['CreepTumor','NydusWorm'])
        except:
            tb = sys.exc_info()[2]
            errmsg = 'PlayerSupply.built_from_drone(unit) expects argument of type ActivePlayerSupply.'
            raise TypeError(errmsg).with_traceback(tb)
            
    def _sync_records(self,frame,cursup):
        if not isinstance(cursup,ActivePlayerSupply):
            tb = sys.exc_info()[2]
            errmsg = 'PlayerSupply._sync_records() expects argument of type ActivePlayerSupply.'
            raise TypeError(errmsg).with_traceback(tb)
#         print('k we got here')
        try:
            # while zerg buildings are in production the drones evolving into buildings
            # are still alive, but shouldn't be counted in the units queue
#             print('calculating the drone offset...')
            drone_offset = sum([self.built_from_drone(u) for u in cursup.production.values()])
#             print('calculated the drone offset')
            for attr in ['production','units','structures']:
#                 print(f'  attr is {attr}')
                current = cursup.__getattribute__(attr)
                record = self.__getattribute__(attr)
                d = {}
#                 print(f'current is {current}')
#                 print(current.values())
#                 print('  goin into loop')
                for unit in current.values():
#                     print(f'    unit is {unit}')
                    key = unit.name
#                     print(f'    key is {key}')
                    self.unit_types.setdefault(key,unit)
                    d[key] = d.get(key,0)+1
#                 print(f'finished tallying entries in {attr}')
                if drone_offset and attr=='units':
#                     print('applying drone offset...')
#                     print(f'  dictionary   : {d}')
#                     print(f'  drone_offset : {drone_offset}')
                    d['Drone'] -= drone_offset
#                     print('drone offset applied...')
                try:
#                     print('I will attempt to update the record now!')
#                     print(f"record is {record}")
#                     print(f"frame is {frame}")
#                     print(f"dict is {d}")
                    record.try_update(frame,d)
                except:
                    print('something wrong when calling try_update_record')
#             print('Now update the main supply record...')
            self.data.try_update(frame,self.count_supply())
#             print('Main supply updated!')
        except:
            print('something has gone terribly wrong in _sync_records')


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
            
    @staticmethod
    def _frames_to_seconds(frames):
        return int(frames/16.0)
    
    @classmethod
    def _frames_to_timestr(cls,frames,useGameTimeStr=True):
        return cls._seconds_to_timestr(frames/16.0,useGameTimeStr)

#     def time_supply_capped(self,useGameTime=True):
#         return self._seconds_to_timestr(self.supply_capped_real_seconds,useGameTime)      
    
    
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
            self.supply[pid]._sync_records(f,acs)
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
                self.supply[pid]._sync_records(f,acs)
            # may need to handle Terran and Protoss events here as well
        except:
            print(f'Unhandled BasicCommandEvent : {event}')
                  
            
    def handleUnitInitEvent(self, event, replay):
        try:
            f,unit,uid,pid,acs = self.unwrapUnitEvent(event)
            acs.production[uid]=unit
            self.supply[pid]._sync_records(f,acs)
        except:
            print(f'Unhandled UnitInitEvent : {event}')
        
    def handleUnitDoneEvent(self, event, replay):
        try:
            f,unit,uid,pid,acs = self.unwrapUnitEvent(event)
            acs.production.pop(uid)
            acs.structures[uid] = unit
            self.supply[pid]._sync_records(f,acs)
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
                    self.supply[pid]._sync_records(f,acs)
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
                    self.supply[pid]._sync_records(f,acs)
        except:
            print(f'Unhandled UnitDiedEvent : {event}')

    def handleEndGame(self, event, replay):
        for player in replay.players:
            player.foo = 'bar'
            # need to do any sorting?
            player.supply = self.supply[player.pid]
            # make up these old numbers
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