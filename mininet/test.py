#!/usr/bin/python

from mininet.net import Mininet
from mininet.topo import Topo
from mininet.link import TCLink
from mininet.log import setLogLevel, info
from mininet.util import pmonitor
from mininet.node import OVSController
from mininet.nodelib import LinuxBridge
from mininet.cli import CLI
from datetime import datetime, timedelta
import random
import signal
import sys
import math
import time
import os
import subprocess
import argparse
import sqlite3
import logging
import shutil
import psutil
from contextlib import closing

class TimerList:	
	def __init__(self):
		self.list = []
		self.ref = datetime.now()

	def refresh(self):
		new_ref = datetime.now()
		if(len(self.list) != 0):
			self.list[0][0] -= (new_ref - self.ref)
		self.ref = new_ref

	def insert(self, time, obj, func):
		self.refresh()
		idx = 0
		t = timedelta(seconds=time)
		for idx in range(len(self.list)):
			if(t < self.list[idx][0]):
				self.list[idx][0] -= t 
				self.list.insert(idx,[t, obj, func])				
				idx = None
				break
			t -= self.list[idx][0]
		if(idx != None):
			self.list.append([t, obj, func])
			
	def check(self):
		self.refresh()
		res = 1
		while(len(self.list)):
			elem = self.list[0]
			if(elem[0] <= timedelta()):
				self.list.pop(0)
				elem[2](elem[1],elem[0])
			else:
				res = self.list[0][0].total_seconds()/timedelta(microseconds=1000).total_seconds()
				break
		return res
	
	def stop(self):
		self.list = []


class Test:
	def __init__(self, n_pubhosts, pubsperhost, n_subhosts, subsperhost, n_ports = 64, loss=0, delay='0ms', delaybool=False,
					lambda_in_pubhost=10, lambda_in_subhost=10, test_time=-1, 
					output=None,
					auxfile=None, 
					pcapfile_outcome="../results/TC-default-outcome.pcap",
					pcapfile_income="../results/TC-default-income.pcap",
					perffile="../results/perf.csv",
					errorfile="../results/error.log"):
		self.popens = {}
		self.perfprocs = {}
		self.timer_list = TimerList()
		self.server = None
		self.serverIP = ""
		self.idle_pubs = []
		self.idle_subs = []
		self.active_pubs = []
		self.active_subs = []
		self.pubsperhost = pubsperhost
		self.subsperhost = subsperhost
		self.lambda_in_pubhost = lambda_in_pubhost
		self.lambda_in_subhost = lambda_in_subhost
		self.test_time = test_time
		self.perffile = open(perffile, "w")
		self.errorfile = open(errorfile, "w")
		self.finalize = False
		
		signal.signal(signal.SIGINT, self._signal_handler)
		test_topo = Topo()

		pubhosts = []
		subhosts = []

		srv = test_topo.addHost( 'srv1' )
		for h in range(1, n_pubhosts+1):
			pubhosts.append(test_topo.addHost( 'hp%s' % h ))
		for h in range(1, n_subhosts+1):
			subhosts.append(test_topo.addHost( 'hs%s' % h ))

		smaster = test_topo.addSwitch('s0_2')
		sloss1 = test_topo.addSwitch('s0_1')
		sloss2 = test_topo.addSwitch('s0_0')
		test_topo.addLink(srv, smaster, loss=0)
		if delaybool:
			test_topo.addLink(smaster, sloss1, loss=0, delay=delay)
		else:
			test_topo.addLink(smaster, sloss1, loss=loss)
		test_topo.addLink(sloss1, sloss2, loss=0)
		self._genTree(test_topo, pubhosts+subhosts, sloss2, n_ports, 1, loss=0)

		self.net = Mininet(topo=test_topo, switch=LinuxBridge, link=TCLink)
		self.net.addNAT().configDefault()
		self.net.start()
		time.sleep(4)

		self.server = self.net['srv1']
		self.serverIP = self.net['srv1'].IP()
		for h in range(1, n_pubhosts+1):
			client = self.net['hp%s' % h]
			self.idle_pubs.append(client)
		for h in range(1, n_subhosts+1):
			client = self.net['hs%s' % h]
			self.idle_subs.append(client)
		
		subcommand = "ip src %s and port %s" % (self.serverIP, get_tshark_port())
		subcommand2 = "tshark -w " + pcapfile_outcome + " -i srv1-eth0 -f " + "\'" + subcommand + "\'"
		tsharkCall = ["su", "-", "detraca", "-c", subcommand2]
		self.popens['outcome-tshark'] = self.server.popen(tsharkCall, stderr=self.errorfile)

		subcommand = "ip dst %s and port %s" % (self.serverIP, get_tshark_port())
		subcommand2 = "tshark -w " + pcapfile_income + " -i s0_1-eth2 -f " + "\'" + subcommand + "\'"
		tsharkCall = ["su", "-", "detraca", "-c", subcommand2]
		self.popens['income-tshark'] = self.net['s0_1'].popen(tsharkCall, stderr=self.errorfile)
			
		if(output != None):
			self.outputfile = open(output,"w")
		else:
			self.outputfile = sys.stdout
		if (auxfile != None):
			self.auxfile = open(auxfile,"w")
		else:
			self.auxfile = open('/dev/null', 'w')

	def _signal_handler(self, sig, frame):
		self.finish(None, None)

	def _genTree(self, test_topo, childs, smaster, n_ports, level, loss=0):
		switches = []
		n_switches = 1
		n_childs = len(childs)
		if(n_childs > n_ports):
			n_switches = int(math.ceil(n_childs/(n_ports-1.)))
			for s in range(1, n_switches+1):
				switches.append(test_topo.addSwitch('s%d_%s' % (level, s)))
		else:
			switches.append(smaster)
		while(len(childs)):
			for s in switches:
				if(len(childs) != 0):
					test_topo.addLink(childs.pop(0), s, loss=loss)
				else:
					break
		if(n_switches > 1):
			return(self._genTree(test_topo, switches, smaster, n_ports, level+1, loss))
		return

	def run(self):
		if(not self.finalize):		
			self.popens[self.server.name] = self.server.popen(serverlaunch(self.idle_pubs.copy(), self.pubsperhost, self.idle_subs.copy(), self.subsperhost, self.server.name, self.serverIP), stderr=self.errorfile)
			self.start_perf(self.server.name, None)
			self.measure_perf(None, None)
			time.sleep(10)
			if(self.lambda_in_pubhost > 0.):
				t = random.expovariate(self.lambda_in_pubhost)
				self.timer_list.insert(t, None, self.arrive_pub)
				self.timer_list.insert(t+0.001, "hp1_1", self.start_perf)
			if(self.lambda_in_subhost > 0.):
				t = random.expovariate(self.lambda_in_subhost)
				self.timer_list.insert(t, None, self.arrive_sub)
				self.timer_list.insert(t+0.001, "hs1_1", self.start_perf)
			if(self.test_time > 0.):
				self.timer_list.insert(self.test_time, None, self.prefinish)

			while(self.popens):
				try:
					host, line = next(pmonitor(self.popens, timeoutms=self.timer_list.check()))
					if(host):
						if(line.startswith('**')):
							self.outputfile.write("%s, %s, %s" % (host, self.net[host[0:host.find('_')]].IP(), line.replace('**', '')))
						else:
							self.auxfile.write("%s, %s" % (host, line))
				except Exception as e:
					pass

		#print("loop end")
		self.outputfile.close()
		self.perffile.close()
		self.errorfile.close()
		self.auxfile.close()
		self.net.stop()
	
	def arrive_pub(self, obj, t):
		if(len(self.idle_pubs) > 0):
			new_pub = self.idle_pubs.pop(0)
			for idx, client in enumerate(publaunch(self.pubsperhost, new_pub.name, self.serverIP)):
				key = new_pub.name + "_" + str(idx+1)
				self.popens[key] = new_pub.popen(client, stderr=self.errorfile)
				self.active_pubs.append(key)
		if(len(self.idle_pubs) > 0):
			self.timer_list.insert(random.expovariate(self.lambda_in_pubhost), None, self.arrive_pub)

	def arrive_sub(self, obj, t):
		if(len(self.idle_subs) > 0):
			new_sub = self.idle_subs.pop(0)
			for idx, client in enumerate(sublaunch(self.subsperhost, new_sub.name, self.serverIP)):
				key = new_sub.name + "_" + str(idx+1)
				self.popens[key] = new_sub.popen(client, stderr=self.errorfile)
				self.active_subs.append(key)
		if(len(self.idle_subs) > 0):
			self.timer_list.insert(random.expovariate(self.lambda_in_subhost), None, self.arrive_sub)

	def start_perf(self, obj, t):
		self.perfprocs[obj] = psutil.Process(self.popens[obj].pid)

	def measure_perf(self, obj, t):
		for host, proc in self.perfprocs.items():
			resources = proc.as_dict(attrs=['cpu_times', 'memory_info', 'cpu_percent'])
			ip = self.net[host].IP() if host == 'srv1' else self.net[host[0:host.find('_')]].IP()
			self.perffile.write("%s, %s, %s, %f, %f, %f, %f, %d, %d, %f\n" % (time.time_ns(), host, ip,
						resources['cpu_times'].user, resources['cpu_times'].system,
						resources['cpu_times'].children_user, resources['cpu_times'].children_system,
						resources['memory_info'].rss, resources['memory_info'].vms,
						resources['cpu_percent']))
		if(not self.finalize):
			self.timer_list.insert(1, None, self.measure_perf)

	def prefinish(self, obj, t):
		self.perfprocs.pop('hp1_1')
		for pub in self.active_pubs:
			if self.popens.get(pub):
				self.popens[pub].send_signal(signal.SIGINT)
		self.timer_list.insert(10, None, self.finish)
		
	def finish(self, obj, t):
		if self.finalize:
			print("Force Finish...")
			for proc in self.popens.values():
				proc.send_signal(signal.SIGKILL)
		else:
			self.finalize = True
			self.timer_list.stop()
			self.popens['srv1'].send_signal(signal.SIGINT)
			for sub in self.active_subs:
				if self.popens.get(sub):
					self.popens[sub].send_signal(signal.SIGINT)
			self.popens['outcome-tshark'].send_signal(signal.SIGINT)
			self.popens['income-tshark'].send_signal(signal.SIGINT)
			try:
				for proc in self.popens.values():
					proc.wait(60)
			except Exception as e:
				self.finish(None, None)
	



if __name__ == '__main__':
	parser = argparse.ArgumentParser(description="Mininet Test")
    
	parser.add_argument(
		"-s",
        "--servertype",
        type=str,
        metavar="coap, mqtt, wt",
		choices=["coap", "mqtt", "wt", "wt_z"],
        required=True,
        help="type of server",
    )

	parser.add_argument(
		"-db",
		"--topicsdatabase",
		type=str,
		required=True,
		help="path to file containing SQL database",
	)

	parser.add_argument(
		"-nt",
		"--ntopics",
		type=int,
		required=True,
		help="path to file containing SQL database",
	)

	parser.add_argument(
        "-l",
        "--pktloss",
        type=int,
		default=0,
        required=False,
    )

	parser.add_argument(
        "-d",
        "--pktdelay",
        type=str,
		default='0ms',
        required=False,
    )


	parser.add_argument(
		"-t",
		"--testtime",
		type=int,
		required=True,
		help="time of testing",
	)

	parser.add_argument(
		"-testdir",
		type=str,
		required=False,
		help="test directory",
	)

	parser.add_argument(
        "-hp",
        "--pubhosts",
        type=int,
        required=False,
    )

	parser.add_argument(
        "-cp",
        "--pubsperhost",
        type=int,
        required=False,
    )

	parser.add_argument(
        "-hs",
        "--subhosts",
        type=int,
        required=False,
    )

	parser.add_argument(
        "-cs",
        "--subsperhost",
        type=int,
        required=False,
    )

	parser.add_argument(
        "--seed",
        type=int,
        required=False,
    )

	parser.add_argument(
        "-dy", "--delaybool", action="store_true", default=False,
    )

	parser.add_argument(
        "-v", "--verbose", action="store_true", help="increase logging verbosity"
    )

	args = parser.parse_args()

	logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )
	
	serversdict = {
		"coap": 
			"/home/detraca/TFM/myenv/bin/python /home/detraca/TFM/aiocoap/coap_server.py --port 5683",
		"mqtt": 
			"mosquitto -c /home/detraca/TFM/mqtt/mosquitto_mininet.conf", 
		"wt": 
			"/home/detraca/TFM/myenv/bin/python /home/detraca/TFM/pubsubaio/server.py -c /home/detraca/TFM/aioquic/aioquic-main/examples/certs/certificate.pem -k /home/detraca/TFM/aioquic/aioquic-main/examples/certs/certificate.key --port 5555 --db /home/detraca/TFM/sqlite/database.db -l /home/detraca/TFM/wireshark/secret",
		"wt_z": 
			"/home/detraca/TFM/myenv/bin/python /home/detraca/TFM/pubsubaio/server.py -c /home/detraca/TFM/aioquic/aioquic-main/examples/certs/certificate.pem -k /home/detraca/TFM/aioquic/aioquic-main/examples/certs/certificate.key --port 5555 --db /home/detraca/TFM/sqlite/database.db -l /home/detraca/TFM/wireshark/secret",
	}
	pubsdict = {
		"coap": 
			"/home/detraca/TFM/myenv/bin/python /home/detraca/TFM/aiocoap/coap_client.py --port 5683",
		"mqtt": 
			"/home/detraca/TFM/myenv/bin/python /home/detraca/TFM/mqtt/mqtt_client.py --port 6666 --ca-certs /home/detraca/TFM/mqtt/certs/mqtt-srv.crt --certfile /home/detraca/TFM/mqtt/certs/sensor00-client.crt --keyfile /home/detraca/TFM/mqtt/certs/sensor00-client.key -k", 
		"wt": 
			"/home/detraca/TFM/myenv/bin/python /home/detraca/TFM/pubsubaio/client.py --user detraca --password 1234 --port 5555 --path '' --ca-certs /home/detraca/TFM/aioquic/aioquic-main/examples/certs/certificate.pem -k",
		"wt_z": 
			"/home/detraca/TFM/myenv/bin/python /home/detraca/TFM/pubsubaio/client.py --user detraca --password 1234 --port 5555 --path '' --ca-certs /home/detraca/TFM/aioquic/aioquic-main/examples/certs/certificate.pem -k",
	}
	subsdict = {
		"coap": 
			"/home/detraca/TFM/myenv/bin/python /home/detraca/TFM/aiocoap/coap_client.py --port 5683",
		"mqtt": 
			"/home/detraca/TFM/myenv/bin/python /home/detraca/TFM/mqtt/mqtt_client.py --port 6666 --ca-certs /home/detraca/TFM/mqtt/certs/mqtt-srv.crt --certfile /home/detraca/TFM/mqtt/certs/sensor00-client.crt --keyfile /home/detraca/TFM/mqtt/certs/sensor00-client.key -k", 
		"wt": 
			"/home/detraca/TFM/myenv/bin/python /home/detraca/TFM/pubsubaio/client.py --user detraca --password 1234 --port 5555 --path '' --ca-certs /home/detraca/TFM/aioquic/aioquic-main/examples/certs/certificate.pem",
		"wt_z": 
			"/home/detraca/TFM/myenv/bin/python /home/detraca/TFM/pubsubaio/client.py --user detraca --password 1234 --port 5555 --path '' --ca-certs /home/detraca/TFM/aioquic/aioquic-main/examples/certs/certificate.pem",
	}

	def serverlaunch(pubhosts, pubsperhost, subhosts, subsperhost, servername, serverIP):
		extra = ""
		if args.servertype == "mqtt":
			with open('/home/detraca/TFM/mqtt/mosquitto_mininet.conf', 'r') as f:
				lines = f.readlines()
			with open('/home/detraca/TFM/mqtt/mosquitto_mininet.conf', 'w') as f:
				for line in lines:
					if line.startswith('listener'):
						line = 'listener 6666 %s\n' % (serverIP)
					f.write(line)
		elif args.servertype == "coap":
			oscore_prepare(pubhosts, pubsperhost, subhosts, subsperhost, servername, serverIP)
			extra = " --host %s -c /home/detraca/TFM/aiocoap/oscore/server/%s.json --topics %s" % (serverIP, servername, ' '.join(topics))
		else:
			extra = " --host %s /home/detraca/TFM/pubsubaio/app/serverapp.py:app" % (serverIP) 
		return serversdict[args.servertype] + extra
	
	def publaunch(n, user, serverIP):
		global topicspubs
		random.shuffle(topicspubs)
		random.shuffle(datas)
		result = []
		cmd = pubsdict[args.servertype] + " --host %s " % (serverIP)
		for i in range(n):
			topic = topicspubs.pop(0)
			if (len(topicspubs) == 0):
				topicspubs = list(topics)
			data = datas.pop(0)
			if args.servertype == "coap":
				cmd = pubsdict[args.servertype] + " --host %s -c /home/detraca/TFM/aiocoap/oscore/clients/%s_%d.json --path %s --pub app=/home/detraca/TFM/pubsubaio/pubs/randompub.py:generic_publish data=/home/detraca/TFM/pubsubaio/pubs/randomdata.py:%s topic=%s" % (serverIP, user, i+1, topic, data, topic)
				result.append(cmd)
			elif args.servertype == "mqtt":
				cmd = pubsdict[args.servertype] + " --host %s --user %s_%d --pub app=/home/detraca/TFM/pubsubaio/pubs/randompub.py:generic_publish data=/home/detraca/TFM/pubsubaio/pubs/randomdata.py:%s topic=%s qos=2" % (serverIP, user, i+1, data, topic)
				result.append(cmd)
			else:
				cmd += "--user %s_%d --pub app=/home/detraca/TFM/pubsubaio/pubs/randompub.py:webtransport_publish data=/home/detraca/TFM/pubsubaio/pubs/randomdata.py:%s topic=%s " % (user, i+1, data, topic)
				if args.servertype == "wt_z":
					cmd += "compression=zlib "
				result = [cmd]
		return result

	def sublaunch(n, user, serverIP):
		random.shuffle(topics)
		result = []
		cmd = pubsdict[args.servertype] + " --host %s " % (serverIP)
		for i in range(n):
			topic = topics[i]
			if args.servertype == "coap":
				cmd = subsdict[args.servertype] + " --host %s -c /home/detraca/TFM/aiocoap/oscore/clients/%s_%d.json --path %s --sub app=/home/detraca/TFM/pubsubaio/subs/sub.py:generic_subscribe topic=%s" % (serverIP, user, i+1, topic, topic)
				result.append(cmd)
			elif args.servertype == "mqtt":
				cmd = subsdict[args.servertype] + " --host %s " % (serverIP) + "--user %s_%d --sub app=/home/detraca/TFM/pubsubaio/subs/sub.py:generic_subscribe topic=%s qos=2" % (user, i+1, topic)
				result.append(cmd)
			else:
				cmd += "--user %s_%d --sub app=/home/detraca/TFM/pubsubaio/subs/sub.py:webtransport_subscribe topic=%s " % (user, i+1, topic)
				if args.servertype == "wt_z":
					cmd += "compression=zlib "
				result = [cmd]
		return result
	
	def get_tshark_port():
		port = 5555
		if args.servertype == "coap":
			port = 5683
		elif args.servertype == "mqtt":
			port = 6666
		return str(port)
	
	def oscore_prepare(pubhosts, pubsperhost, subhosts, subsperhost, servername, serverIP):
		def create_file(filename, content):
			with open(filename, 'w') as f:
				f.write(content)
			os.chown(filename, uid, gid)
		def fill_dir(hostlist, hostclients, ispub):
			for host in hostlist:
				for i in range(1, hostclients+1):
					hostname = host.name + "_" + str(i)
					hostid = "%x" % (((int(host.name[2:]))<<11)|(i<<1)|int(ispub))
					server_clients.append(hostname)
					create_file(os.path.join(clients_dir, hostname + ".json"), 
		 				'{"coap://%s/*": { "oscore": { "contextfile": "/home/detraca/TFM/aiocoap/oscore/clients/%s/" } }}' % (serverIP, hostname)
					)
					tmp_dir = os.path.join(clients_dir, hostname)
					os.makedirs(tmp_dir)
					os.chown(tmp_dir, uid, gid)
					create_file(os.path.join(tmp_dir, "settings.json"),
		 				'{"sender-id_ascii": "%s","recipient-id_ascii": "%s","secret_ascii": "%s"}' % (hostid, servername, password)
		 			)
					tmp_dir = os.path.join(server_dir, hostname)
					os.makedirs(tmp_dir)
					os.chown(tmp_dir, uid, gid)
					create_file(os.path.join(tmp_dir, "settings.json"), 
		 				'{"recipient-id_ascii": "%s","sender-id_ascii": "%s","secret_ascii": "%s"}' % (hostid, servername, password)
					)
		root_dir = "/home/detraca/TFM/aiocoap/"
		work_dir = os.path.join(root_dir, 'oscore')
		clients_dir = os.path.join(work_dir, 'clients')
		server_dir = os.path.join(work_dir, 'server')
		uid = int(os.environ.get("SUDO_UID"))
		gid = int(os.environ.get("SUDO_GID"))
		server_clients = []
		if os.path.exists(work_dir):
			shutil.rmtree(work_dir)
		os.makedirs(work_dir)
		os.chown(work_dir, uid, gid)
		os.makedirs(clients_dir)
		os.chown(clients_dir, uid, gid)
		os.makedirs(server_dir)
		os.chown(server_dir, uid, gid)
		password = "password12345678"
		fill_dir(pubhosts, pubsperhost, True)
		fill_dir(subhosts, subsperhost, False)
		serverjson = os.path.join(server_dir, servername + ".json")
		with open(serverjson, 'w') as f:
			f.write("{")
			for i in range(len(server_clients)-1):
				client = server_clients[i]
				f.write('":%s": { "oscore": { "contextfile": "/home/detraca/TFM/aiocoap/oscore/server/%s/" } },' % (client, client))
			client = server_clients[i+1]
			f.write('":%s": { "oscore": { "contextfile": "/home/detraca/TFM/aiocoap/oscore/server/%s/" } }' % (client, client))
			f.write("}")
		os.chown(serverjson, uid, gid)
	

	testdir = args.testdir if args.testdir else "/home/detraca/TFM/mininet/pruebas/outputs"
	output =  os.path.join(testdir, args.servertype) + "_out.csv"
	#auxfile = os.path.join(testdir, args.servertype) + "_aux.txt"
	#errorfile = os.path.join(testdir, args.servertype) + "_error.log"
	auxfile = errorfile = "/dev/null"
	perffile = os.path.join(testdir, args.servertype) + "_perf.csv"
	pcapfile_outcome = os.path.join(testdir, args.servertype) + "_outcome.pcap"
	pcapfile_income = os.path.join(testdir, args.servertype) + "_income.pcap"
	tsharkfile_outcome = os.path.join(testdir, args.servertype) + "_outcome_tshark.csv"
	tsharkfile_income = os.path.join(testdir, args.servertype) + "_income_tshark.csv"

	hp = args.pubhosts if args.pubhosts else 1
	cp = args.pubsperhost if args.pubsperhost else 1 
	hs = args.subhosts if args.subhosts else 1 
	cs = args.subsperhost if args.subsperhost else 1

	seed = args.seed if args.seed else 0

	import sys
	from pcaptocsv import generate_pcap_csv
	sys.path.append("../sqlite") # absolute path to sqlite's folder
	from dbupdate import create_topics_and_perms

	create_topics_and_perms(args.topicsdatabase, args.ntopics, hp, cp, hs, cs, '1234')

	topics = []
	with closing(sqlite3.connect(args.topicsdatabase)) as connection:
		with closing(connection.cursor()) as cursor:
			rows = cursor.execute("SELECT name from topics LIMIT %d" % (args.ntopics)).fetchall()
			topics = [item[0] for item in rows]

	topicspubs = list(topics)
	datas = ["JSON%i" % (i) for i in range(1,21)]
	random.seed(seed)  		
	
	Test(hp, cp, hs, cs, 
      	test_time=args.testtime,
	    loss=args.pktloss,
	    delay = args.pktdelay,
	    delaybool = args.delaybool, 
		lambda_in_pubhost=10, 
		lambda_in_subhost=10,
		output=output,
		auxfile=auxfile,
		perffile=perffile, 
		pcapfile_outcome=pcapfile_outcome,
		pcapfile_income=pcapfile_income,  
		errorfile=errorfile).run()
	
	os.system("sudo mn -c")
	pids = subprocess.run(['pidof', '/home/detraca/TFM/myenv/bin/python'], stdout=subprocess.PIPE).stdout.decode('utf-8')
	if pids != '':
		os.system("sudo kill -9 " + pids)

	generate_pcap_csv(pcapfile_outcome, tsharkfile_outcome)
	generate_pcap_csv(pcapfile_income, tsharkfile_income)
