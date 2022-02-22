# -*- coding: utf-8 -*-
from __future__ import absolute_import, print_function, unicode_literals, division

from sc2reader.log_utils import loggable
from builtins import property as _property
#from dataclasses import dataclass
from collections import defaultdict, UserList
from typing import NamedTuple
from copy import copy
import sys

class ActivePlayerSupply:
    def __init__(self):
        self.last_command = None
        self.preproduction = {'training':{},'eggs':{},'morph_type':None}
        self.production = {}
        self.units = {}
        self.structures = {}
    
    def morph_unit(self,frame,utype):
        for larva_id in self.preproduction['eggs'].pop(frame):
            self.production[larva_id]=utype
            
    def flush(self,frame,syncf,utype=None):
        for f in [f for f in self.preproduction['eggs'] if f<frame]:
            self.morph_unit(f,self.preproduction['morph_type'])
            syncf(f,self)
        if utype:
            self.morph_unit(frame,utype)
            syncf(frame,self)
            self.preproduction['morph_type']=utype

class TimeSeries(UserList):      
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
            
    def gt(self,time,tunit='frame'):
        pass
        
    def lt(self,time,tunit='frame'):
        pass
            
    def at(self,time,tunit='frame'):
        def strfmt(item):
            if type(item)==str:
                return ':'.join([f"{int(n):02d}" for n in item.split(':')])
            return item
        
        i=-1
        for item in self:
            if strfmt(time) < strfmt(item[0]):
                return self[max(i,0)]
            i += 1
            
    def tf(self,t_unit='frame'):
        if t_unit=='frame':
            return self
        elif t_unit=='sec':
            return self.__class__([(self._frames_to_seconds(f),d) for f,d in self])
        elif t_unit in ['timestr','str']:
            return self.__class__([(self._frames_to_timestr(f),d) for f,d in self])
        else:
            tb = sys.exc_info()[2]
            errmsg="t_unit should be one of ['frame','sec','str','timestr']"
            raise ValueError(errmsg).with_traceback(tb)
        
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
    
    def _repr_pretty_(self,p,cycle):
        if cycle:
            p.text(f"{self.__class__.__name__}(...)")
        else:
            pre = f"{self.__class__.__name__}(["
            with p.group(len(pre), pre, "])"):
                for idx, item in enumerate(self):
                    if idx:
                        p.text(',')
                        p.breakable()
                    p.pretty(item) 

    
class SupplyTuple(NamedTuple):
    workers: int
    army: int
    capacity: int
    
    def __get_supply(self):
        return self.workers+self.army
    supply=_property(__get_supply,None,None,'Total supply.')
    
    def __repr__(self):
        return tuple.__repr__(self)
    
docstrings = {"workers":"Supply of workers active and in production.",
"army":"Supply of army active and in production.",
"supply":"Supply of workers+army active and in production.",
"capacity":"Total available supply capacity."}

for key,val in docstrings.items():
    setattr(getattr(SupplyTuple,key),"__doc__",val)
    
# This is just a TimeSeries object that can filter the data 
# entry using any of the methods defined for SupplyTuple
class SupplyTimeSeries(TimeSeries):
    pass

def funcgen(fname):
    return lambda self: TimeSeries([(f,getattr(d,fname)) for f,d in self])

for fname in dir(SupplyTuple):
    if fname not in dir(tuple) and not fname.startswith('_'):
        setattr(SupplyTimeSeries,
                "__get_"+fname,
                funcgen(fname))
        setattr(SupplyTimeSeries,
                fname,
                property(getattr(SupplyTimeSeries,"__get_"+fname),
                         None,
                         None,
                         getattr(getattr(SupplyTuple,fname),"__doc__")))
    
class PlayerSupply:
    """ Data structure to hold supply information. """
    
    def __init__(self):
        """ Create a new _Supply instance. """
        self.data = SupplyTimeSeries([(0,SupplyTuple(0,0,0))]) 
        self.production = TimeSeries([(0,{})]) # (frame, production queue at frame)
        self.units = TimeSeries([(0,{})]) # (frame, units queue at frame)
        self.structures = TimeSeries([(0,{})]) # (frame, structures queue at frame)
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
            return SupplyTuple(w,a,c)
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
        try:
            # while zerg buildings are in production the drones evolving into buildings
            # are still alive, but shouldn't be shown in the units queue
            drone_offset = sum([self.built_from_drone(u) for u in cursup.production.values()])
            for attr in ['production','units','structures']:
                current = cursup.__getattribute__(attr)
                record = self.__getattribute__(attr)
                d = {}
                for unit in current.values():
                    key = unit.name
                    self.unit_types.setdefault(key,unit)
                    d[key] = d.get(key,0)+1
                if drone_offset and attr=='units':
                    d['Drone'] -= drone_offset
                record.try_update(frame,d)
            self.data.try_update(frame,self.count_supply())
        except:
            print('Something has gone wrong in _sync_records')

    

@loggable
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
                acs.flush(frame,self.supply[pid]._sync_records)
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

    def handleCommandEvent(self, event, replay):
        try:
            if event.player:
                self.active_supply[event.player.pid].last_command=event
        except:
            print(f"Unhandled CommandEvent {event}")
            
    def handleCommandManagerStateEvent(self, event, replay):
        """
        This means the last CommandEvent got repeated, so if we need to
        make a copy and pass it along.
        """
        try:
            if event.player:
                acs = self.active_supply[event.player.pid]
                if acs.last_command.name=="BasicCommandEvent":
                    new_event = copy(acs.last_command)
                    new_event.frame = event.frame
                    self.handleBasicCommandEvent(new_event,replay)
        except:
            print(f"Unhandled CommandManagerStateEvent: {event}")
            
    def handleUnitTypeChangeEvent(self, event, replay):
        try:
            f,unit,uid,pid,acs = self.unwrapUnitEvent(event)
            print()
            race=event.unit.owner.detail_data['race']
            if race=='Zerg':
                if event.unit_type_name=="Egg":
                    # spend larva from units and put egg in preprod queue
                    # where it waits for a corresponding "Morph" event
                    acs.units.pop(uid)
                    acs.preproduction['eggs'].setdefault(f,[]).append(uid)
                elif event.unit_type_name=="Larva":
                    # remove egg from production and add larva back to units
                    acs.production.pop(uid) 
                    acs.units[uid]=unit
                elif event.unit_type_name.endswith('Cocoon'):
                    acs.units.pop(uid)
                    acs.production[uid]=unit
                elif event.unit_type_name.endswith('Burrowed'):
                    pass
                elif unit.is_army:
                    acs.production.pop(uid) 
                    acs.units[uid]=unit
                # are there more UnitTypeChangeEvents for other unit morphs (lurker,broods)?
            elif race=='Terran':
                pass
            elif race=='Protoss':
                pass
            else:
                return
            self.supply[pid]._sync_records(f,acs)
        except:
            print(f'at frame {event.frame}...')
            print(f'Unhandled UnitTypeChangeEvent : {event}')
        
    def handleBasicCommandEvent(self, event, replay):
        try:
            f = event.frame
            pid = event.player.pid
            if event.has_ability:
                acs = self.active_supply[pid]
                if event.ability.name.startswith('MorphTo'):
                    pass # handle ravagers, lurkers, broods, banes, ovies (maybe don't need)
                elif event.ability.name.startswith('Morph'):
                    unit = event.ability.build_unit
                    acs.flush(f,self.supply[pid]._sync_records,unit)
                elif event.ability.name.startswith('Train'):
                    uname = event.ability.build_unit.name
                    acs.preproduction['training'].setdefault('cc',[]).append(uname)
                    print(acs.preproduction['training'])
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
            #player.giant = Giant()
            # need to do any sorting?
            player.supply = self.supply[player.pid]
            # make up these old numbers
            player.current_food_used = dict(sorted(player.current_food_used.items()))
            player.current_food_made = dict(sorted(player.current_food_made.items()))
            #player.supply.data.sort(key=lambda x: x[0])
        print('end of game!')
            