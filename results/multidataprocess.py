import os, pickle, argparse
import pandas as pd


def dataprocess(basedir, loss_delay, protocol):
    dirstr = basedir

    #load data into a DataFrame object:
    df = pd.read_csv(
        "%s/%s_out.csv" % (dirstr, protocol), 
        names=['client', 'ip', 'ts', 'topic', 'event', 'hash', 'msglength'],
        skipinitialspace=True,
    )
    windf = pd.read_csv(
        "%s/%s_income_tshark.csv" % (dirstr, protocol), 
        names=['ts', 'srcip', 'dstip', 'framelength'],
        skipinitialspace=True,
    )
    woutdf = pd.read_csv(
        "%s/%s_outcome_tshark.csv" % (dirstr, protocol), 
        names=['ts', 'srcip', 'dstip', 'framelength'],
        skipinitialspace=True,
    )
    pdf = pd.read_csv(
        "%s/%s_perf.csv" % (dirstr, protocol), 
        names=['ts', 'client', 'ip', 'usertime', "systemtime", "userctime", "systemctime", "rss", "vms", "cpu"],
        skipinitialspace=True,
    )

    #adjust column types and positions
    df['hash'] = df['hash'].astype('Int64')
    df['msglength'] = df['msglength'].astype('Int64')
    col = df.pop("ts")
    df.insert(0, 'ts', col.astype('datetime64[ns]'))
    windf['ts'] = windf['ts'].astype('datetime64[ns]')
    woutdf['ts'] = woutdf['ts'].astype('datetime64[ns]')
    pdf['ts'] = pdf['ts'].astype('datetime64[ns]')
    windf['framelength'] = windf['framelength'].astype('Int64')
    woutdf['framelength'] = woutdf['framelength'].astype('Int64')

    #mix df with pdf
    df = pd.concat([df, pdf])
    df.insert(1, 'host', df.apply(lambda x: x['client'][0:x['client'].find('_')], axis=1))
    #fill 'event' for perf traces
    df.loc[df['event'].isna(), 'event'] = 'PERF_INFO'
    #mix df with wdf
    df = pd.concat([df, windf, woutdf])
    df.sort_values(by=['ts'], inplace=True)
    df.insert(0, 'id', df.index)

    #fill 'host' and 'event' for tshark traces and deletes 'srcip' and 'dstip'
    hostIPs = df[df['event'] != 'PERF_INFO'].groupby('ip')['host'].first()
    df.loc[df['host'].isna(), 'event'] = 'PKTOUT'
    df.set_index('srcip', inplace=True)
    df['host'] = df['host'].fillna(hostIPs)
    df.loc[df['host'].isna(), 'event'] = 'PKTIN'
    df.set_index('dstip', inplace=True)
    df['host'] = df['host'].fillna(hostIPs)
    df.reset_index(inplace=True)
    df.drop(['ip', 'dstip'], axis=1, inplace=True)

    #calculate load parameter f(x)=sumtopics(pubs*subs)
    df['pubcnt'] = df[df['event'] == 'CONNECTED_PUBLISHER'].groupby('topic')['event'].cumcount() + 1
    df['pubcnt'] = df.groupby('topic')['pubcnt'].ffill().astype('Int64')
    df['pubcnt'] = df['pubcnt'].fillna(0)
    df['subcnt'] = df[df['event'] == 'CONNECTED_SUBSCRIBER'].groupby('topic')['event'].cumcount() + 1
    df['subcnt'] = df.groupby('topic')['subcnt'].ffill().astype('Int64')
    df['subcnt'] = df['subcnt'].fillna(0)
    df['load'] = df[df['event'] == 'CONNECTED_PUBLISHER']['subcnt']
    df['load'] = df[df['event'] == 'CONNECTED_SUBSCRIBER']['pubcnt']
    df['load'] = df['load'].fillna(0).cumsum()

    #number publishings
    df['sender'] = df[df['event'] == 'PUBLISHING']['client']
    df['sender'] = df.groupby('hash')['sender'].ffill()
    df['seqnum'] = df[df['event'] == 'PUBLISHING'].groupby('client')['event'].cumcount().astype('Int64') + 1
    df['seqnum'] = df.groupby('hash')['seqnum'].ffill()

    #calculate stats
    eventcounts = df.groupby(['topic', 'event'])['event'].count()
    suboks = eventcounts.xs('CONNECTED_SUBSCRIBER', level=1)
    suberrors = eventcounts.xs('CONNECTING_SUBSCRIBER', level=1).sub(suboks, fill_value=0)
    puboks = eventcounts.xs('CONNECTED_PUBLISHER', level=1)
    puberrors = eventcounts.xs('CONNECTING_PUBLISHER', level=1).sub(puboks, fill_value=0)
    publishings = eventcounts.xs('PUBLISHING', level=1)
    recieveds = eventcounts.xs('RECIEVED', level=1)
    closeds = eventcounts.xs('CLOSED_SUBSCRIBER', level=1).add(eventcounts.xs('CLOSED_PUBLISHER', level=1), fill_value=0)

    recverrors = df.groupby(['topic', 'hash']).filter(lambda x: (x['event'] != 'PUBLISHING').all()).groupby('topic')['event'].count()
    recvlosses = df[df['event'] == 'PUBLISHING'].groupby(['topic', 'hash'])['subcnt'].sum()
    recvlosses = recvlosses.sub(df[df['event'] == 'RECIEVED'].groupby(['topic', 'hash'])['subcnt'].count(), fill_value=0).astype('Int64').clip(lower=0).groupby('topic').sum()
    outseqerrs = df[df['event'] == 'RECIEVED'].groupby(['topic', 'sender', 'client'])['seqnum'].cummax()
    df.loc[df['event'] == 'RECIEVED', 'outseqerrs'] = outseqerrs
    outseqerrs = df[df['seqnum'] != df['outseqerrs']].groupby('topic')['seqnum'].count()
    tpublishings = df[df['event'].isin(['CONNECTING_PUBLISHER', 'CLOSED_PUBLISHER'])].groupby(['client', 'topic'])['ts'].aggregate(['first', 'last'])
    tpublishings = (((tpublishings['last'] - tpublishings['first'])/pd.Timedelta(seconds=1)) + 1).astype(int).groupby('topic').sum()
    trecieveds = df[df['event'] == 'PUBLISHING'].groupby('topic')['subcnt'].sum()

    stats = pd.concat([suberrors, puberrors, suboks, puboks, tpublishings, publishings, trecieveds, recieveds, recverrors, recvlosses/recieveds, outseqerrs, closeds], axis=1).fillna(0).astype('Int64')
    stats.columns=['suberrors', 'puberrors', 'suboks', 'puboks', 'exp_publishings', 'publishings', 'exp_recieveds', 'recieveds', 'recverrors', 'recvlosses', 'outseqerrs', 'closeds']

    tot_stats = stats.sum()
    tot_stats['recvlosses_rel'] = tot_stats['recvlosses']/tot_stats['exp_recieveds']
    tot_stats['recieveds_rel'] = tot_stats['recieveds']/tot_stats['exp_recieveds']

    m = df[df['event'].isin(['PUBLISHING','RECIEVED'])].groupby('host')['msglength'].aggregate(['count','sum'])
    f = df[df['event'].isin(['PKTIN','PKTOUT'])].groupby('host')['framelength'].aggregate(['count','sum'])
    eff = m.div(f)
    tot_stats['frames_eff'] = eff['count'].mean()
    tot_stats['bytes_eff'] = eff['sum'].mean()

    perf_infos = df.copy()[df['event'] == 'PERF_INFO'][['client', 'usertime', 'systemtime', 'userctime', 'systemctime']].groupby('client').last().sum(axis=1)
    publs_recvs = df[(df['client'].isin(['hp1_1', 'hs1_1'])) & (df['event'].isin(['PUBLISHING', 'RECIEVED']))].groupby('client')['event'].count()
    tot_stats['recvs_sub'] = publs_recvs['hs1_1']
    tot_stats['publs_pub'] = publs_recvs['hp1_1']
    tot_stats['perf_sub'] = perf_infos['hs1_1']
    tot_stats['perf_pub'] = perf_infos['hp1_1']
    tot_stats['perf_srv'] = perf_infos['srv1']

    mem_infos = df.copy()[df['event'] == 'PERF_INFO'][['client', 'rss']].groupby('client').last().sum(axis=1)
    tot_stats['mem_srv'] = mem_infos['srv1']

    #custom
    total_pkts = df[df['event'].isin(['PKTIN', 'PKTOUT'])]['id'].count()
    tot_stats['outsec_rel'] = tot_stats['outseqerrs']/tot_stats['recieveds']
    tot_stats['recvlosses_rel2'] = tot_stats['recvlosses']/(tot_stats['recieveds']+tot_stats['recvlosses'])
    tot_stats['perf_sub_rel'] = perf_infos['hs1_1']/publs_recvs['hs1_1']
    tot_stats['perf_pub_rel'] = perf_infos['hp1_1']/publs_recvs['hp1_1']
    tot_stats['perf_srv_rel'] = perf_infos['srv1']/tot_stats['publishings']

    connecting = df[df['event'] == 'CONNECTING_SUBSCRIBER'].groupby(['client', 'topic'])['ts'].min()
    connected = df[df['event'] == 'CONNECTED_SUBSCRIBER'].groupby(['client', 'topic'])['ts'].max()
    a = ((connected.sub(connecting))/pd.Timedelta(nanoseconds=1)).dropna().astype('int64').reset_index()['ts']
    conexion = a.agg(['min', 'max', 'mean'])
    tot_stats['con_min'] = conexion['min']
    tot_stats['con_max'] = conexion['max']
    tot_stats['con_mean'] = conexion['mean']/1e9

    pubts = df[df['event'] == 'PUBLISHING'].groupby('hash')['ts'].first()
    df.set_index('hash', inplace=True)
    df.loc[df['event'] == 'RECIEVED', 'ptime'] = pubts
    df.reset_index(inplace=True)
    df['ptime'] = ((df['ts'] - df['ptime'])/pd.Timedelta(nanoseconds=1)).astype('Int64')
    #delete every first recieved ptime value (msg could be buffered)
    df.loc[df['id'].isin(df[df['event'] == 'RECIEVED'].groupby(['client', 'topic'], as_index=False).first()['id']), 'ptime'] = pd.NA
    pubts = df['ptime'].agg(['min', 'max', 'mean'])
    tot_stats['pubt_min'] = pubts['min']
    tot_stats['pubt_max'] = pubts['max']
    tot_stats['pubt_mean'] = pubts['mean']/1e9

    return [tot_stats]


def get_losses(basedir):
    res = []
    for dir in os.listdir(basedir):
        try:
            if dir.startswith('l'):
                res.append(int(dir[dir.find('l')+1:]))
        except:
            pass
    return sorted(res)

def get_delays(basedir):
    res = []
    for dir in os.listdir(basedir):
        try:
            if dir.startswith('d'):
                res.append(int(dir[dir.find('d')+1:dir.find('ms')]))
        except:
            pass
    return sorted(res)

def calculate_mean(datas):
    size = len(datas)
    if size == 0:
        return None
    elif size == 1:
        return datas[0]
    else:
        try:
            mean_stats = datas[0][0]
            for i in range(1, size):
                mean_stats = pd.concat([mean_stats, datas[i][0]], axis=1)
            mean_stats = mean_stats.transpose()
            q1 = mean_stats.quantile(0.25)
            q3 = mean_stats.quantile(0.75)
            iqr = q3 - q1
            lower = q1 - 1.25*iqr
            upper = q3 + 1.25*iqr
            mean_stats = mean_stats.mask(mean_stats < lower)
            mean_stats = mean_stats.mask(mean_stats > upper)
            return [mean_stats.mean()]
        except:
            import traceback
            traceback.print_exc()



if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Mininet Test")

    parser.add_argument(
        "-nc", 
        "--nc", 
        action="store_true", 
        default=False,
    )

    parser.add_argument(
        "-dy", 
        "--delaybool", 
        action="store_true", 
        default=False,
    )

    parser.add_argument(
        "--basedir",
        type=str,
        required=False,
        default="./experiments",
    )

    parser.add_argument(
        "--timedir",
        type=str,
        required=False,
        default="t120",
    )

    parser.add_argument(
        "--seeddir",
        type=str,
        required=False,
        default="s0",
    )

    args = parser.parse_args()

    basedir = args.basedir
    results_loss = {'wt_z': {}, 'wt': {}, 'mqtt': {}, 'coap': {}}
    results_delay = {'wt_z': {}, 'wt': {}, 'mqtt': {}, 'coap': {}}
    if args.nc:
        actualdir = os.path.join(args.basedir, args.timedir)
        if args.delaybool:
            outputfile = os.path.join(args.basedir, 'results_delay.pickle')
            delays = get_delays(actualdir)
            for protocol in results_delay.keys():
                for d in range(len(delays)):
                    delay = delays[d]
                    print(delay)
                    delaydir = os.path.join(actualdir, 'd'+str(delay)+'ms')
                    try:
                        data = dataprocess(os.path.join(delaydir, args.seeddir), delays[d], protocol)
                        results_delay.get(protocol).update({delay: data})
                    except:
                        import traceback
                        traceback.print_exc()
            with open(outputfile, 'wb') as f:
                pickle.dump(results_delay, f)
        else:
            outputfile = os.path.join(args.basedir, 'results_loss.pickle')
            losses = get_losses(actualdir)
            for protocol in results_loss.keys():
                for l in range(len(losses)):
                    loss = losses[l]
                    print(loss)
                    lossdir = os.path.join(actualdir, 'l'+str(loss))
                    try:
                        data = dataprocess(os.path.join(lossdir, args.seeddir), losses[l], protocol)
                        results_loss.get(protocol).update({loss: data})
                    except:
                        import traceback
                        traceback.print_exc()
            with open(outputfile, 'wb') as f:
                pickle.dump(results_loss, f)


    else:
        for dir in os.listdir(args.basedir):
            try:
                actualdir = os.path.join(args.basedir, dir)
                if os.path.isdir(actualdir):
                    outputfile_delay = os.path.join(args.basedir, 'results_delay_' + str(dir) + '.pickle')
                    outputfile_loss = os.path.join(args.basedir, 'results_loss_' + str(dir) + '.pickle')
                    actualdir = os.path.join(args.basedir, dir, args.timedir)
                    delays = get_delays(actualdir)
                    losses = get_losses(actualdir)

                    for protocol in results_loss.keys():

                        for d in range(len(delays)):
                            delay = delays[d]
                            print("Processing dir=%s protocol=%s  delay=%dms" % (dir, protocol, delay))
                            delaydir = os.path.join(actualdir, 'd'+str(delay)+'ms')
                            delay_datas = []
                            for seed in os.listdir(delaydir):
                                try:
                                    data = dataprocess(os.path.join(delaydir, seed), delays[d], protocol)
                                    delay_datas.append(data)
                                except:
                                    import traceback
                                    traceback.print_exc()
                            mean_data = calculate_mean(delay_datas)
                            if mean_data is not None:
                                results_delay.get(protocol).update({delay/1000: mean_data})

                        for l in range(len(losses)):
                            loss = losses[l]
                            print("Processing dir=%s protocol=%s  loss=%d" % (dir, protocol, loss))
                            lossdir = os.path.join(actualdir, 'l'+str(loss))
                            loss_datas = []
                            for seed in os.listdir(lossdir):
                                try:
                                    data = dataprocess(os.path.join(lossdir, seed), losses[l], protocol)
                                    loss_datas.append(data)
                                except:
                                    import traceback
                                    traceback.print_exc()
                            mean_data = calculate_mean(loss_datas)
                            if mean_data is not None:
                                results_loss.get(protocol).update({loss: mean_data})

                    with open(outputfile_delay, 'wb') as f:
                        pickle.dump(results_delay, f)

                    with open(outputfile_loss, 'wb') as f:
                        pickle.dump(results_loss, f)

                    results_loss = {'wt_z': {}, 'wt': {}, 'mqtt': {}, 'coap': {}}
                    results_delay = {'wt_z': {}, 'wt': {}, 'mqtt': {}, 'coap': {}}
            except:
                pass