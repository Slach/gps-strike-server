# coding=utf-8
import sockjs.tornado
import json
import hashlib
import ConfigParser
import geo

class GPSStrikeConfig:
    cfg = ConfigParser.ConfigParser()

    @staticmethod
    def parse(file_name):
        print( "Parsing %s..." % file_name)
        GPSStrikeConfig.cfg.read(file_name)
        if not GPSStrikeConfig.cfg.has_section('game') or not GPSStrikeConfig.cfg.has_section('server'):
            raise ConfigParser.NoSectionError('[game] and [server] section required in server.cfg')
        print( "...DONE")

class GPSStrikeException(Exception):
    AnyError=0
    Auth=1
    UnknownDevice=2
    TargetNotInGame=3
    WrongAttack=4

class GPSStrikeConnection(sockjs.tornado.SockJSConnection):
    pool = set()
    PLAYERS = {}
    cmd_list = {}

    @staticmethod
    def fill_cmd_list():
        GPSStrikeConnection.cmd_list = {
            'connect': GPSStrikeConnection.cmd_connect,
            'coordinates': GPSStrikeConnection.cmd_coordinates,
            'energy_attack': GPSStrikeConnection.cmd_energy_attack,
            'mech_attack': GPSStrikeConnection.cmd_mech_attack

        }


    def on_open(self, request):
        print( "Received connection from " + request.ip)
        GPSStrikeConnection.pool.add(self)

    def on_message(self, msg):

        data = json.loads(msg)
        print( "received msg=%s\n" % msg)
        try:
            if 'cmd' not in data or data['cmd'] not in GPSStrikeConnection.cmd_list:
                raise GPSStrikeException(0,'Unknown client command')
            self.auth(data)
            GPSStrikeConnection.cmd_list[data['cmd']](self,data)

        except GPSStrikeException as (err_code,err_message):
            msg = { 'error': { 'code':err_code,'message':err_message } }
            self.send_json(msg)


    def on_close(self):
        print("connections close")
        GPSStrikeConnection.pool.remove(self)

    def auth(self,data):
        h=hashlib.sha1()
        h.update(data["uuid"])
        h.update(GPSStrikeConfig.cfg.get('server','password'))
        if data['auth_k'] != h.hexdigest():
            raise GPSStrikeException(GPSStrikeException.Auth,'authorization error')

    def send_json(self,data):
        msg = json.dumps(data)
        print( "send_json msg=%s\n" % msg)
        self.send(msg)


    def send_json_all(self, data,send_me=False):
        msg = json.dumps(data)
        if send_me == False:
            GPSStrikeConnection.pool.remove(self)

        print( "send_json_all\n{0:>s}\nto {1:d} clients\n".format(msg, len(GPSStrikeConnection.pool)))
        self.broadcast(GPSStrikeConnection.pool,msg)

        if send_me == False:
            GPSStrikeConnection.pool.add(self)

    def check_in_players(self,uuid):
        if uuid not in GPSStrikeConnection.PLAYERS:
            raise GPSStrikeException(GPSStrikeException.UnknownDevice,"devise %s not in PLAYERS" % uuid)

    def check_distance(self,d,r,msg):
        if (d > r):
            raise GPSStrikeException(GPSStrikeException.TargetNotInGame,msg % (d,r))

    def check_sector(self,player,target,angle,player2):
        target_angle = geo.great_circle_angle(player,target,geo.geographic_northpole)
        player2_angle = geo.great_circle_angle(player,player2,geo.geographic_northpole)
        return geo.distance(player,player2) <= geo.distance(player,target) and abs(target_angle-player2_angle) <= angle / 2

    def check_player_more(self,player,key,value):
        if (float(player[key]) <= float(value)):
            raise GPSStrikeException(GPSStrikeException.AnyError,'Need %s > %s' % (key,value))

    def check_player_less(self,player,key,value):
        if (float(player[key]) >= float(value)):
            raise GPSStrikeException(GPSStrikeException.AnyError,'Need %s < %s' % (key,value))

    def cmd_connect(self,data):
        cfg  = GPSStrikeConfig.cfg
        if data['uuid'] not in GPSStrikeConnection.PLAYERS:
            GPSStrikeConnection.PLAYERS[data['uuid']] = {
                'login': data['login'],
                'coordinates': data['coordinates'],
                'health': cfg.get('game','health'),
                'energy': cfg.get('game','energy')
            }
            print( "Adding new device %s to PLAYERS" % data['uuid'])
        else:
            print( "Update existing device %s in PLAYERS" % data['uuid'])
            GPSStrikeConnection.PLAYERS[data['uuid']]['login'] = data['login']
            GPSStrikeConnection.PLAYERS[data['uuid']]['coordinates'] = data['coordinates']
        # сообщение мне
        msg = { 'cmd':'game', 'game':{}}
        for opt in cfg.options('game'):
            msg['game'][opt] = cfg.getfloat('game',opt)
        msg['players'] = []
        for uuid in GPSStrikeConnection.PLAYERS:
            player = GPSStrikeConnection.PLAYERS[uuid]
            player['uuid'] = uuid
            msg['players'].append(player)
        self.send_json(msg)
        # сообщение всем
        msg = {'cmd': 'connect', 'uuid': data['uuid']}
        for key in ['login','health','coordinates']:
            msg[key] = GPSStrikeConnection.PLAYERS[data['uuid']][key]
        self.send_json_all(msg)



    def cmd_coordinates(self,data):
        self.check_in_players(data['uuid'])
        GPSStrikeConnection.PLAYERS[data['uuid']]['coordinates']=data['coordinates']
        msg = { 'cmd':'coordinates', 'uuid': data['uuid'] }
        for key in ['coordinates','health']:
            msg[key] = GPSStrikeConnection.PLAYERS[data['uuid']][key]
        self.send_json_all(msg)


    def cmd_energy_attack(self,data):
        self.check_in_players(data['uuid'])
        cfg = GPSStrikeConfig.cfg

        msg = { 'cmd': 'energy_attack',
                'uuid': data['uuid'],
                'target': data['target'],
                'angle':data['angle'],
                'attack':data['attack']
        }

        msg['damaged_players'] = []

        game_center = geo.xyz(cfg.getfloat('game','latitude'),cfg.getfloat('game','longitude'))
        target = geo.xyz(float(data['target']['lat']),float(data['target']['lng']))
        player = GPSStrikeConnection.PLAYERS[data['uuid']]
        self.check_player_more(player,'health',0)

        player_center = geo.xyz(float(player['coordinates']['lat']),float(player['coordinates']['lng']))
        self.check_distance(geo.distance(game_center,target),float(cfg.get('game','radius')),"distance from center to target %f more then maximum game radius %f")
        self.check_distance(geo.distance(player_center,target),float(cfg.get('game','energy_distance')),"distance from player to target %f more then maximum energy distance %f")

        if (data['angle'] > cfg.get('game','energy_angle')):
            raise GPSStrikeException(GPSStrikeException.WrongAttack,'attack angle %s > %s' % (data['angle'], cfg.get('game','energy_angle')) )

        data['attack'] = float(data['attack'])
        self.check_player_more(player,'energy',data['attack'])

        # @todo need energy damage calculcation formula
        damage = data['attack']
        if damage > cfg.get('game','energy_attack'):
            raise GPSStrikeException(GPSStrikeException.WrongAttack,'attack power %s > %s' % (damage, cfg.get('game','energy_attack')) )

        player['energy'] = float(player['energy']) - damage

        for uuid in GPSStrikeConnection.PLAYERS:
            player2 = GPSStrikeConnection.PLAYERS[uuid]
            player2_center = geo.xyz(float(player2['coordinates']['lat']), float(player2['coordinates']['lng']))
            if uuid != data['uuid'] and float(player2['health']) > 0.0 and self.check_sector(player_center, target, float(data['angle']),player2_center):
                    player2['health'] = float(player2['health']) - float(data['attack'])
                    if player2['health'] < 0.0:
                        player2['health'] = 0
                    d_player={}
                    for key in ['uuid','login','coordinates','health']:
                        d_player[key] = player2[key]
                    d_player['damage']=damage
                    msg['damaged_players'].append(d_player)

        self.send_json_all(data=msg,send_me=True)

    def cmd_mech_attack(self,data):
        self.check_in_players(data['uuid'])
        cfg = GPSStrikeConfig.cfg

        msg = { 'cmd': 'mech_attack',
                'uuid': data['uuid'],
                'target': data['target'],
                'radius':data['radius'],
                'attack':data['attack']
        }

        msg['damaged_players'] = []

        game_center = geo.xyz(cfg.getfloat('game','latitude'),cfg.getfloat('game','longitude'))
        target = geo.xyz(float(data['target']['lat']),float(data['target']['lng']))
        player = GPSStrikeConnection.PLAYERS[data['uuid']]
        self.check_player_more(player,'health',0)

        player_center = geo.xyz(float(player['coordinates']['lat']),float(player['coordinates']['lng']))
        self.check_distance(geo.distance(game_center,target),float(cfg.get('game','radius')),"distance from center to target %f more then maximum game radius %f")
        self.check_distance(geo.distance(player_center,target),float(cfg.get('game','mech_distance')),"distance from player to target %f more then maximum mech distance %f")

        if (data['radius'] > cfg.get('game','mech_radius')):
            raise GPSStrikeException(GPSStrikeException.WrongAttack,'attack radius %s > %s' % (data['radius'], cfg.get('game','mech_radius')) )

        data['attack'] = float(data['attack'])
        self.check_player_more(player,'energy',data['attack'])

        # @todo need mech damage calculcation formula
        damage = data['attack']
        if damage > cfg.get('game','mech_attack'):
            raise GPSStrikeException(GPSStrikeException.WrongAttack,'attack power %s > %s' % (damage, cfg.get('game','mech_attack')) )

        player['energy'] = float(player['energy']) - damage

        for uuid in GPSStrikeConnection.PLAYERS:
            player2 = GPSStrikeConnection.PLAYERS[uuid]
            player2_center = geo.xyz(float(player2['coordinates']['lat']), float(player2['coordinates']['lng']))
            if uuid != data['uuid'] and float(player2['health']) > 0.0 and geo.distance(target, player2_center) <= float(data['radius']):
                player2['health'] = float(player2['health']) - float(data['attack'])
                if player2['health'] < 0.0:
                    player2['health'] = 0
                d_player={}
                for key in ['uuid','login','coordinates','health']:
                    d_player[key] = player2[key]
                d_player['damage']=damage
                msg['damaged_players'].append(d_player)

        self.send_json_all(data=msg,send_me=True)
