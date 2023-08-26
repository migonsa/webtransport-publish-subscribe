import subprocess, sys, logging, argparse, os, signal
from pathlib import Path
from time import time as get_time


class MultiTest:
    def __init__(self, time, loss, delay, nruns, seeds, ntopics, servers, pubhosts, pubsperhost, subhosts, subsperhost, db, savedir, delaybool) -> None:
        self.time = time
        self.loss = loss
        self.delay = delay
        self.nruns = nruns
        self.seeds = seeds
        self.ntopics = ntopics
        self.servers = servers
        self.actualdir = None
        self.hp = pubhosts
        self.cp = pubsperhost
        self.hs = subhosts
        self.cs = subsperhost
        self.db = db
        self.delaybool = delaybool
        self.close = False
        testdir = "hp%d_%d_hs%d_%d_top%d" % (self.hp, self.cp, self.hs, self.cs, self.ntopics)
        self.testdir = os.path.join(savedir, testdir)
        p = Path(self.testdir)
        p.mkdir(parents=True, exist_ok=True, mode=0o777)
        p.chmod(mode=0o777)

    def run(self):
        out = open("/dev/null", "w")
        #out = sys.stdout
        loss_or_delay = self.delay if self.delaybool else self.loss
        with open("/home/detraca/TFM/mininet/pruebas/outputs/results/multitest.log", "w") as file:
            file.write("Starting multitest...\n")
            file.flush()
            for t in self.time:
                for n in range(self.nruns):
                    try:
                        seed = self.seeds[n]
                    except IndexError:
                        print("No specified seed, creating new one...")
                        seed = int.from_bytes(os.urandom(8), sys.byteorder)
                    for ld in loss_or_delay:
                        self.get_or_create_dir(t, seed, ld)
                        for s in self.servers:
                            if not self.close:
                                params = self.get_params(t, seed, ld, s)
                                if self.delaybool:
                                    debugstr = "delay=%s" % (ld)
                                else:
                                    debugstr = "loss=%d%%" % (ld)
                                print("Launching test time=%d run=%d %s server=%s ... " % (t, n, debugstr, s))
                                file.write("\n\nLaunching test time=%d run=%d %s server=%s ..." % (t, n, debugstr, s))
                                file.flush()
                                start = get_time()
                                self.proc = subprocess.Popen('sudo python /home/detraca/TFM/mininet/pruebas/test.py ' + params,
                                        shell=True, 
                                        stdout=file,
                                        stderr=file)
                                self.proc.wait()
                                end = get_time() - start
                                print("Done in %f seconds.\n" % (end))
                                file.write("Finished (time=%f)\n" % (end))
                                file.flush()
                            else:
                                file.write("Forced Finished\n")

    def get_params(self, time, seed, loss_or_delay, server):
        params = "-db %s -testdir %s -nt %d -s %s -t %d" % (self.db, self.actualdir, self.ntopics, server, time)
        params += " -hp %d -cp %d -hs %d -cs %d --seed %d" % (self.hp, self.cp, self.hs, self.cs, seed)
        if self.delaybool:
            params += " -d %s -dy" % (loss_or_delay)
        else:
            params += " -l %d" % (loss_or_delay)
        return params
    
    def get_or_create_dir(self, time, seed, loss_or_delay):
        self.actualdir = os.path.join(self.testdir, "t%d" % (time))
        if self.delaybool:
            self.actualdir = os.path.join(self.actualdir, "d%s" % (loss_or_delay))
        else:
            self.actualdir = os.path.join(self.actualdir, "l%d" % (loss_or_delay))
        self.actualdir = os.path.join(self.actualdir, "s%d" % (seed))
        p = Path(self.actualdir)
        p.mkdir(parents=True, exist_ok=True, mode=0o777)
        p.chmod(mode=0o777)

    def signal_handler(self, sig, frame):
        print("FORCE FINISH MULTITEST")
        self.close = True
        if self.proc:
            self.proc.send_signal(signal.SIGKILL)
        os.system("sudo mn -c")
        pids = subprocess.run(['pidof', '/home/detraca/TFM/myenv/bin/python'], stdout=subprocess.PIPE).stdout.decode('utf-8')
        if pids != '':
            os.system("sudo kill -9 " + pids)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Mininet Test")
    
    parser.add_argument(
        "-nt",
        "--ntopics",
        type=int,
        required=False,
    )

    parser.add_argument(
        "-t",
        "--testtime",
        type=int,
        nargs='*',
        required=False,
    )

    parser.add_argument(
        "-l",
        "--pktloss",
        type=int,
        nargs='*',
        required=False,
    )

    parser.add_argument(
        "-d",
        "--pktdelay",
        type=str,
        nargs='*',
        required=False,
    )

    parser.add_argument(
        "-r",
        "--nruns",
        type=int,
        required=False,
    )

    parser.add_argument(
        "-seeds",
        "--seeds",
        type=int,
        nargs='*',
        required=False,
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
		"-db",
		"--topicsdatabase",
		type=str,
		required=False,
		help="path to file containing SQL database",
	)

    parser.add_argument(
		"--savedir",
		type=str,
		required=True,
		help="path to save directory",
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
    

    total_time = get_time()
    nruns = 25
    servers = ["wt_z", "wt", "mqtt", "coap"]  
    ntopics = 10
    seeds = [int.from_bytes(os.urandom(8), sys.byteorder) for i in range (nruns)]
    time = [120]
    loss = [i for i in range(0, 33, 3)]
    delay = ['%ims' % (i) for i in range(0, 2200, 200)]
    savedir = "../results"
    db = "../sqlite/database.db"

    multitest_time = get_time()
    run = MultiTest(time, loss, delay, nruns, seeds, ntopics, servers, 20, 1, 100, 1, db, savedir, False)
    signal.signal(signal.SIGTSTP, run.signal_handler)
    run.run()
    print("\nTime hp20_1_hs_100_1 loss: ", get_time()-multitest_time)

    multitest_time = get_time()
    run = MultiTest(time, loss, delay, nruns, seeds, ntopics, servers, 2, 10, 10, 10, db, savedir, False)
    signal.signal(signal.SIGTSTP, run.signal_handler)
    run.run()
    print("\nTime hp2_10_hs_10_10 loss: ", get_time()-multitest_time)

    multitest_time = get_time()
    run = MultiTest(time, loss, delay, nruns, seeds, ntopics, servers, 20, 1, 100, 1, db, savedir, True)
    signal.signal(signal.SIGTSTP, run.signal_handler)
    run.run()
    print("Time hp20_1_hs_100_1 delay: ", get_time()-multitest_time)

    multitest_time = get_time()
    run = MultiTest(time, loss, delay, nruns, seeds, ntopics, servers, 2, 10, 10, 10, db, savedir, True)
    signal.signal(signal.SIGTSTP, run.signal_handler)
    run.run()
    print("Time hp2_10_hs_10_10 delay: ", get_time()-multitest_time)
    
    print("\nTOTAL EXEC TIME: ", get_time()-total_time)