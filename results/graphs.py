import pickle, atexit, os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import FormatStrFormatter, AutoMinorLocator


def get_figure_stats(results, var):
    x = {}
    y = {}
    for p in results.keys():
        x_aux = []
        y_aux = []
        for i in results.get(p).items():
            x_aux.append(i[0])
            y_aux.append(i[1][0][var])
        x.update({p: x_aux})
        y.update({p: y_aux})
    return (x, y)

def get_smooth_line(x, y):
    X_ = x
    Y_ = y
    return X_, Y_


pickles = [('./results_loss_hp20_1_hs100_1_top10.pickle', 'sep/loss/', True, False),
           ('./results_delay_hp20_1_hs100_1_top10.pickle', 'sep/delay/', False, False),
           ('./results_loss_hp2_10_hs10_10_top10.pickle', 'tog/loss/', True, True),
           ('./results_delay_hp2_10_hs10_10_top10.pickle','tog/delay/', False, True)]

plt.rcParams["font.family"] = "Courier New"
figure_size = (8.5, 8.5)
title_size = 28
legend_size = 20
legend_title_size = 20
label_size = 24
labelpad = 10
xticks_size = yticks_size = 20
alpha = 0.7
dot_size = 120
linewidth= 3

wt_z_color = '#0033FF'
wt_color = '#8000FF'
mqtt_color = '#26A200'
coap_color = '#C37B00'
all_color = '#8E8E8E'

wt_z_label = 'WTPS_Z'
wt_label  = 'WTPS'
mqtt_label  = 'MQTT'
coap_label = 'COAP_PS'
all_label = 'ALL'
label_loc = 'best'

savedir = "./graphs"


for i in pickles:
    with open(i[0], 'rb') as f:
        results = pickle.load(f)
        d = i[1]
        loss = i[2]
        multiclient = i[3]

        ld_title = 'packet loss' if loss else 'delay'
        ld_xlabel = 'Packet loss (%)' if loss else 'Delay (s)'
    
    

    var = 'con_mean'
    x,y = get_figure_stats(results, var)
    figure = plt.figure()
    figure.set_size_inches(figure_size)
    axes = figure.add_subplot(1,1,1)
    x_smooth,y_smooth = get_smooth_line(x['wt_z'], y['wt_z'])
    axes.plot(x_smooth, y_smooth, color=wt_z_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['wt'], y['wt'])
    axes.plot(x_smooth, y_smooth, color=wt_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['mqtt'], y['mqtt'])
    axes.plot(x_smooth, y_smooth, color=mqtt_color, alpha=alpha, linewidth=linewidth)
    axes.scatter(x['wt_z'], y['wt_z'], label=wt_z_label, color=wt_z_color, alpha=alpha, s=dot_size)
    axes.scatter(x['wt'], y['wt'], label=wt_label, color=wt_color, alpha=alpha, s=dot_size)
    axes.scatter(x['mqtt'], y['mqtt'], label=mqtt_label, color=mqtt_color, alpha=alpha, s=dot_size)

    axes.legend(loc=label_loc, fontsize=legend_size, title_fontsize=legend_title_size)
    axes.set_title("Mean connection time\nwith respect to " + ld_title, fontsize=title_size)
    axes.set_xlabel(ld_xlabel, fontsize=label_size, labelpad=labelpad)
    axes.set_ylabel('Time (s)', fontsize=label_size, labelpad=labelpad)
    plt.xticks(fontsize=xticks_size)
    plt.yticks(fontsize=yticks_size)
    if not loss:
        plt.ylim(0, 9)
        plt.xlim(0, 1.3)
    axes.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    axes.xaxis.set_minor_locator(AutoMinorLocator())
    axes.yaxis.set_minor_locator(AutoMinorLocator())
    axes.tick_params(which='both', width=2)
    axes.tick_params(which='major', length=7)
    axes.tick_params(which='minor', length=4)
    plt.savefig(os.path.join(savedir, d, 'conn_time.pdf'))



    var = 'pubt_mean'
    x,y = get_figure_stats(results, var)
    if loss:
        x['coap'] = [x for x in x['coap'][:-4]]
        y['coap'] = [x for x in y['coap'][:-4]]
    figure = plt.figure()
    figure.set_size_inches(figure_size)
    axes = figure.add_subplot(1,1,1)
    x_smooth,y_smooth = get_smooth_line(x['wt_z'], y['wt_z'])
    axes.plot(x_smooth, y_smooth, color=wt_z_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['wt'], y['wt'])
    axes.plot(x_smooth, y_smooth, color=wt_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['mqtt'], y['mqtt'])
    axes.plot(x_smooth, y_smooth, color=mqtt_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['coap'], y['coap'])
    axes.plot(x_smooth, y_smooth, color=coap_color, alpha=alpha, linewidth=linewidth)
    axes.scatter(x['wt_z'], y['wt_z'], label=wt_z_label, color=wt_z_color, alpha=alpha, s=dot_size)
    axes.scatter(x['wt'], y['wt'], label=wt_label, color=wt_color, alpha=alpha, s=dot_size)
    axes.scatter(x['mqtt'], y['mqtt'], label=mqtt_label, color=mqtt_color, alpha=alpha, s=dot_size)
    axes.scatter(x['coap'], y['coap'], label=coap_label, color=coap_color, alpha=alpha, s=dot_size)

    axes.legend(loc=label_loc, fontsize=legend_size, title_fontsize=legend_title_size)
    axes.set_title("Mean publication time\nwith respect to " + ld_title, fontsize=title_size)
    axes.set_xlabel(ld_xlabel, fontsize=label_size, labelpad=labelpad)
    axes.set_ylabel('Time (s)', fontsize=label_size, labelpad=labelpad)
    plt.xticks(fontsize=xticks_size)
    plt.yticks(fontsize=yticks_size)
    if not loss:
        plt.locator_params(axis='x', nbins=5)
    axes.yaxis.set_major_formatter(FormatStrFormatter('%2d'))
    axes.xaxis.set_minor_locator(AutoMinorLocator())
    axes.yaxis.set_minor_locator(AutoMinorLocator())
    axes.tick_params(which='both', width=2)
    axes.tick_params(which='major', length=7)
    axes.tick_params(which='minor', length=4)
    plt.savefig(os.path.join(savedir, d, 'publ_time.pdf'))



    var = 'publishings'
    x,y = get_figure_stats(results, var)
    y['wt_z'] = [x/y['wt_z'][0] for x in y['wt_z']]
    y['wt'] = [x/y['wt'][0] for x in y['wt']]
    y['mqtt'] = [x/y['mqtt'][0]for x in y['mqtt']]
    y['coap'] = [x/y['coap'][0] for x in y['coap']]
    figure = plt.figure()
    figure.set_size_inches(figure_size)
    axes = figure.add_subplot(1,1,1)
    x_smooth,y_smooth = get_smooth_line(x['wt_z'], y['wt_z'])
    axes.plot(x_smooth, y_smooth, color=wt_z_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['wt'], y['wt'])
    axes.plot(x_smooth, y_smooth, color=wt_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['mqtt'], y['mqtt'])
    axes.plot(x_smooth, y_smooth, color=mqtt_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['coap'], y['coap'])
    axes.plot(x_smooth, y_smooth, color=coap_color, alpha=alpha, linewidth=linewidth)
    axes.scatter(x['wt_z'], y['wt_z'], label=wt_z_label, color=wt_z_color, alpha=alpha, s=dot_size)
    axes.scatter(x['wt'], y['wt'], label=wt_label, color=wt_color, alpha=alpha, s=dot_size)
    axes.scatter(x['mqtt'], y['mqtt'], label=mqtt_label, color=mqtt_color, alpha=alpha, s=dot_size)
    axes.scatter(x['coap'], y['coap'], label=coap_label, color=coap_color, alpha=alpha, s=dot_size)

    axes.legend(loc=label_loc, fontsize=legend_size, title_fontsize=legend_title_size)
    axes.set_title("Relative publications\nwith respect to " + ld_title, fontsize=title_size)
    axes.set_xlabel(ld_xlabel, fontsize=label_size, labelpad=labelpad)
    axes.set_ylabel('Relative publications', fontsize=label_size, labelpad=labelpad)
    plt.xticks(fontsize=xticks_size)
    plt.yticks(fontsize=yticks_size)
    if not loss:
        plt.locator_params(axis='x', nbins=5)
    axes.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    axes.xaxis.set_minor_locator(AutoMinorLocator())
    axes.yaxis.set_minor_locator(AutoMinorLocator())
    axes.tick_params(which='both', width=2)
    axes.tick_params(which='major', length=7)
    axes.tick_params(which='minor', length=4)
    plt.savefig(os.path.join(savedir, d, 'publ_total.pdf'))



    var = 'recvlosses_rel2'
    x,y = get_figure_stats(results, var)
    y['coap'] = [x*1000 for x in y['coap']]
    figure = plt.figure()
    figure.set_size_inches(figure_size)
    axes = figure.add_subplot(1,1,1)
    x_smooth,y_smooth = get_smooth_line(x['mqtt'], y['mqtt'])
    axes.plot(x_smooth, y_smooth, color=all_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['coap'], y['coap'])
    axes.plot(x_smooth, y_smooth, color=coap_color, alpha=alpha, linewidth=linewidth)
    axes.scatter(x['mqtt'], y['mqtt'], label='REST', color=all_color, alpha=alpha, s=dot_size)
    axes.scatter(x['coap'], y['coap'], label=coap_label, color=coap_color, alpha=alpha, s=dot_size)

    axes.legend(loc=label_loc, fontsize=legend_size, title_fontsize=legend_title_size)
    axes.set_title("Relative lost publications\nwith respect to " + ld_title, fontsize=title_size)
    axes.set_xlabel(ld_xlabel, fontsize=label_size, labelpad=labelpad)
    axes.set_ylabel('Lost publications (‰)', fontsize=label_size, labelpad=labelpad)
    plt.xticks(fontsize=xticks_size)
    plt.yticks(fontsize=yticks_size)

    axes.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    if not loss:
        plt.locator_params(axis='x', nbins=5)
    else:
        if not multiclient:
            axes.yaxis.set_major_formatter(FormatStrFormatter('%2d'))
    axes.xaxis.set_minor_locator(AutoMinorLocator())
    axes.yaxis.set_minor_locator(AutoMinorLocator())
    axes.tick_params(which='both', width=2)
    axes.tick_params(which='major', length=7)
    axes.tick_params(which='minor', length=4)
    plt.savefig(os.path.join(savedir, d, 'recv_loss.pdf'))



    var = 'outsec_rel'
    x,y = get_figure_stats(results, var)
    y['wt'] = [x*100 for x in y['wt']]
    figure = plt.figure()
    figure.set_size_inches(figure_size)
    axes = figure.add_subplot(1,1,1)
    if loss:
        x_smooth,y_smooth = get_smooth_line(x['wt'], y['wt'])
        axes.plot(x_smooth, y_smooth, color=wt_color, alpha=alpha, linewidth=linewidth)
        axes.scatter(x['wt'], y['wt'], label=wt_label, color=wt_color, alpha=alpha, s=dot_size)
        x_smooth,y_smooth = get_smooth_line(x['mqtt'], y['mqtt'])
        axes.plot(x_smooth, y_smooth, color=all_color, alpha=alpha, linewidth=linewidth)
        axes.scatter(x['mqtt'], y['mqtt'], label='REST', color=all_color, alpha=alpha, s=dot_size)
    else:
        x_smooth,y_smooth = get_smooth_line(x['mqtt'], y['mqtt'])
        axes.plot(x_smooth, y_smooth, color=all_color, alpha=alpha, linewidth=linewidth)
        axes.scatter(x['mqtt'], y['mqtt'], label='ALL', color=all_color, alpha=alpha, s=dot_size)
    
    axes.legend(loc=label_loc, fontsize=legend_size, title_fontsize=legend_title_size)
    axes.set_title("Relative out-of-order publications\nwith respect to " + ld_title, fontsize=title_size)
    axes.set_xlabel(ld_xlabel, fontsize=label_size, labelpad=labelpad)
    axes.set_ylabel('Out-of-order publications (%)', fontsize=label_size, labelpad=labelpad)
    plt.xticks(fontsize=xticks_size)
    plt.yticks(fontsize=yticks_size)

    axes.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    if not loss:
        plt.locator_params(axis='x', nbins=5)
        plt.locator_params(axis='y', nbins=1)
        axes.yaxis.set_major_formatter(FormatStrFormatter('%1d'))
    axes.xaxis.set_minor_locator(AutoMinorLocator())
    axes.yaxis.set_minor_locator(AutoMinorLocator())
    axes.tick_params(which='both', width=2)
    axes.tick_params(which='major', length=7)
    axes.tick_params(which='minor', length=4)
    plt.savefig(os.path.join(savedir, d, 'recv_outseq.pdf'))



    var = 'bytes_eff'
    x,y = get_figure_stats(results, var)
    figure = plt.figure()
    figure.set_size_inches(figure_size)
    axes = figure.add_subplot(1,1,1)
    x_smooth,y_smooth = get_smooth_line(x['wt_z'], y['wt_z'])
    axes.plot(x_smooth, y_smooth, color=wt_z_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['wt'], y['wt'])
    axes.plot(x_smooth, y_smooth, color=wt_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['mqtt'], y['mqtt'])
    axes.plot(x_smooth, y_smooth, color=mqtt_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['coap'], y['coap'])
    axes.plot(x_smooth, y_smooth, color=coap_color, alpha=alpha, linewidth=linewidth)
    axes.scatter(x['wt_z'], y['wt_z'], label=wt_z_label, color=wt_z_color, alpha=alpha, s=dot_size)
    axes.scatter(x['wt'], y['wt'], label=wt_label, color=wt_color, alpha=alpha, s=dot_size)
    axes.scatter(x['mqtt'], y['mqtt'], label=mqtt_label, color=mqtt_color, alpha=alpha, s=dot_size)
    axes.scatter(x['coap'], y['coap'], label=coap_label, color=coap_color, alpha=alpha, s=dot_size)

    axes.legend(loc=label_loc, fontsize=legend_size, title_fontsize=legend_title_size)
    axes.set_title("Network bytes efficiency\nwith respect to " + ld_title, fontsize=title_size)
    axes.set_xlabel(ld_xlabel, fontsize=label_size, labelpad=labelpad)
    axes.set_ylabel('Efficiency', fontsize=label_size, labelpad=labelpad)
    
    plt.xticks(fontsize=xticks_size)
    plt.yticks(fontsize=yticks_size)
    plt.locator_params(axis='x', nbins=7)
    axes.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    axes.xaxis.set_minor_locator(AutoMinorLocator())
    axes.yaxis.set_minor_locator(AutoMinorLocator())
    axes.tick_params(which='both', width=2)
    axes.tick_params(which='major', length=7)
    axes.tick_params(which='minor', length=4)
    plt.savefig(os.path.join(savedir, d, 'bytes_eff.pdf'))



    if not multiclient and not loss:
        var = 'perf_sub_rel'
        x,y = get_figure_stats(results, var)
        a_sub_coap = y['coap'][0]*1000
        a_sub_mqtt = y['mqtt'][0]*1000
        a_sub_wt = y['wt'][0]*1000
        a_sub_wt_z = y['wt_z'][0]*1000
    
    elif multiclient and not loss:
        var = 'perf_sub_rel'
        x,y = get_figure_stats(results, var)

        b_sub_coap = y['coap'][0]*1000
        b_sub_mqtt = y['mqtt'][0]*1000
        b_sub_wt = y['wt'][0]*1000
        b_sub_wt_z = y['wt_z'][0]*1000

        figure = plt.figure()
        figure.set_size_inches(10, 8.5)
        axes = figure.add_subplot(1,1,1)
        ind = np.arange(2)
        width = 0.1
        
        axes.bar(ind, (a_sub_coap,b_sub_coap), width=width, label=coap_label, color=coap_color, alpha=alpha)
        axes.bar(ind+width, (a_sub_mqtt,b_sub_mqtt), width=width, label=mqtt_label, color=mqtt_color, alpha=alpha)
        axes.bar(ind+2*width, (a_sub_wt,b_sub_wt), width=width, label=wt_label, color=wt_color, alpha=alpha)
        axes.bar(ind+3*width, (a_sub_wt_z,b_sub_wt_z), width=width, label=wt_z_label, color=wt_z_color, alpha=alpha)
        
        axes.legend(loc=label_loc, fontsize=legend_size, title_fontsize=legend_title_size)
        axes.set_title("Subscriber CPU usage", fontsize=title_size)
        axes.set_xlabel("Type of experiment", fontsize=label_size, labelpad=labelpad)
        axes.set_ylabel('CPU time per publication (ms)', fontsize=label_size, labelpad=labelpad)
        
        plt.xticks(ind + 3*width / 2, ('Single', 'Multi'), fontsize=xticks_size)
        plt.yticks(fontsize=yticks_size)
        axes.yaxis.set_minor_locator(AutoMinorLocator())
        axes.tick_params(which='both', width=2)
        axes.tick_params(which='major', length=7)
        axes.tick_params(which='minor', length=4)
        plt.savefig(os.path.join(savedir, d, 'perf_sub.pdf'))



    if not multiclient and not loss:
        var = 'perf_pub_rel'
        x,y = get_figure_stats(results, var)
        a_pub_coap = y['coap'][0]*1000
        a_pub_mqtt = y['mqtt'][0]*1000
        a_pub_wt = y['wt'][0]*1000
        a_pub_wt_z = y['wt_z'][0]*1000
    
    elif multiclient and not loss:
        var = 'perf_pub_rel'
        x,y = get_figure_stats(results, var)

        b_pub_coap = y['coap'][0]*1000
        b_pub_mqtt = y['mqtt'][0]*1000
        b_pub_wt = y['wt'][0]*1000
        b_pub_wt_z = y['wt_z'][0]*1000

        figure = plt.figure()
        figure.set_size_inches(10, 8.5)
        axes = figure.add_subplot(1,1,1)
        ind = np.arange(2)
        width = 0.1
        
        axes.bar(ind, (a_pub_coap,b_pub_coap), width=width, label=coap_label, color=coap_color, alpha=alpha)
        axes.bar(ind+width, (a_pub_mqtt,b_pub_mqtt), width=width, label=mqtt_label, color=mqtt_color, alpha=alpha)
        axes.bar(ind+2*width, (a_pub_wt,b_pub_wt), width=width, label=wt_label, color=wt_color, alpha=alpha)
        axes.bar(ind+3*width, (a_pub_wt_z,b_pub_wt_z), width=width, label=wt_z_label, color=wt_z_color, alpha=alpha)
        
        axes.legend(loc=label_loc, fontsize=legend_size, title_fontsize=legend_title_size)
        axes.set_title("Publisher CPU usage", fontsize=title_size)
        axes.set_xlabel("Type of experiment", fontsize=label_size, labelpad=labelpad)
        axes.set_ylabel('CPU time per publication (ms)', fontsize=label_size, labelpad=labelpad)
        
        plt.xticks(ind + 3*width / 2, ('Single', 'Multi'), fontsize=xticks_size)
        plt.yticks(fontsize=yticks_size)
        axes.yaxis.set_minor_locator(AutoMinorLocator())
        axes.tick_params(which='both', width=2)
        axes.tick_params(which='major', length=7)
        axes.tick_params(which='minor', length=4)
        plt.savefig(os.path.join(savedir, d, 'perf_pub.pdf'))



    if not multiclient and not loss:
        var = 'perf_srv_rel'
        x,y = get_figure_stats(results, var)
        a_srv_coap = y['coap'][0]*1000
        a_srv_mqtt = y['mqtt'][0]*1000
        a_srv_wt = y['wt'][0]*1000
        a_srv_wt_z = y['wt_z'][0]*1000
    
    elif multiclient and not loss:
        var = 'perf_srv_rel'
        x,y = get_figure_stats(results, var)

        b_srv_coap = y['coap'][0]*1000
        b_srv_mqtt = y['mqtt'][0]*1000
        b_srv_wt = y['wt'][0]*1000
        b_srv_wt_z = y['wt_z'][0]*1000

        figure = plt.figure()
        figure.set_size_inches(10, 8.5)
        axes = figure.add_subplot(1,1,1)
        ind = np.arange(2)
        width = 0.1
        
        axes.bar(ind, (a_srv_coap,b_srv_coap), width=width, label=coap_label, color=coap_color, alpha=alpha)
        axes.bar(ind+width, (a_srv_mqtt,b_srv_mqtt), width=width, label=mqtt_label, color=mqtt_color, alpha=alpha)
        axes.bar(ind+2*width, (a_srv_wt,b_srv_wt), width=width, label=wt_label, color=wt_color, alpha=alpha)
        axes.bar(ind+3*width, (a_srv_wt_z,b_srv_wt_z), width=width, label=wt_z_label, color=wt_z_color, alpha=alpha)
        
        axes.legend(loc=label_loc, fontsize=legend_size, title_fontsize=legend_title_size)
        axes.set_title("Server/Broker CPU usage", fontsize=title_size)
        axes.set_xlabel("Type of experiment", fontsize=label_size, labelpad=labelpad)
        axes.set_ylabel('CPU time per publication (ms)', fontsize=label_size, labelpad=labelpad)
        
        plt.xticks(ind + 3*width / 2, ('Single', 'Multi'), fontsize=xticks_size)
        plt.yticks(fontsize=yticks_size)
        axes.yaxis.set_minor_locator(AutoMinorLocator())
        axes.tick_params(which='both', width=2)
        axes.tick_params(which='major', length=7)
        axes.tick_params(which='minor', length=4)
        plt.savefig(os.path.join(savedir, d, 'perf_srv.pdf'))



    var = 'perf_sub_rel'
    x,y = get_figure_stats(results, var)
    y['wt_z'] = [x/y['wt_z'][0] for x in y['wt_z']]
    y['wt'] = [x/y['wt'][0] for x in y['wt']]
    y['mqtt'] = [x/y['mqtt'][0]for x in y['mqtt']]
    y['coap'] = [x/y['coap'][0] for x in y['coap']]
    figure = plt.figure()
    figure.set_size_inches(figure_size)
    axes = figure.add_subplot(1,1,1)
    x_smooth,y_smooth = get_smooth_line(x['wt_z'], y['wt_z'])
    axes.plot(x_smooth, y_smooth, color=wt_z_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['wt'], y['wt'])
    axes.plot(x_smooth, y_smooth, color=wt_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['mqtt'], y['mqtt'])
    axes.plot(x_smooth, y_smooth, color=mqtt_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['coap'], y['coap'])
    axes.plot(x_smooth, y_smooth, color=coap_color, alpha=alpha, linewidth=linewidth)
    axes.scatter(x['wt_z'], y['wt_z'], label=wt_z_label, color=wt_z_color, alpha=alpha, s=dot_size)
    axes.scatter(x['wt'], y['wt'], label=wt_label, color=wt_color, alpha=alpha, s=dot_size)
    axes.scatter(x['mqtt'], y['mqtt'], label=mqtt_label, color=mqtt_color, alpha=alpha, s=dot_size)
    axes.scatter(x['coap'], y['coap'], label=coap_label, color=coap_color, alpha=alpha, s=dot_size)

    axes.legend(loc=label_loc, fontsize=legend_size, title_fontsize=legend_title_size)
    axes.set_title("Subscriber CPU usage\nwith respect to " + ld_title, fontsize=title_size)
    axes.set_xlabel(ld_xlabel, fontsize=label_size, labelpad=labelpad)
    axes.set_ylabel('Relative CPU time per publication', fontsize=label_size, labelpad=labelpad)
    
    plt.xticks(fontsize=xticks_size)
    plt.yticks(fontsize=yticks_size)
    plt.locator_params(axis='x', nbins=7)
    axes.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    if loss:
        axes.yaxis.set_major_formatter(FormatStrFormatter('%2d'))
    axes.xaxis.set_minor_locator(AutoMinorLocator())
    axes.yaxis.set_minor_locator(AutoMinorLocator())
    axes.tick_params(which='both', width=2)
    axes.tick_params(which='major', length=7)
    axes.tick_params(which='minor', length=4)
    plt.savefig(os.path.join(savedir, d, 'perf_sub_rel.pdf'))



    var = 'perf_pub_rel'
    x,y = get_figure_stats(results, var)
    y['wt_z'] = [x/y['wt_z'][0] for x in y['wt_z']]
    y['wt'] = [x/y['wt'][0] for x in y['wt']]
    y['mqtt'] = [x/y['mqtt'][0]for x in y['mqtt']]
    y['coap'] = [x/y['coap'][0] for x in y['coap']]
    figure = plt.figure()
    figure.set_size_inches(figure_size)
    axes = figure.add_subplot(1,1,1)
    x_smooth,y_smooth = get_smooth_line(x['wt_z'], y['wt_z'])
    axes.plot(x_smooth, y_smooth, color=wt_z_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['wt'], y['wt'])
    axes.plot(x_smooth, y_smooth, color=wt_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['mqtt'], y['mqtt'])
    axes.plot(x_smooth, y_smooth, color=mqtt_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['coap'], y['coap'])
    axes.plot(x_smooth, y_smooth, color=coap_color, alpha=alpha, linewidth=linewidth)
    axes.scatter(x['wt_z'], y['wt_z'], label=wt_z_label, color=wt_z_color, alpha=alpha, s=dot_size)
    axes.scatter(x['wt'], y['wt'], label=wt_label, color=wt_color, alpha=alpha, s=dot_size)
    axes.scatter(x['mqtt'], y['mqtt'], label=mqtt_label, color=mqtt_color, alpha=alpha, s=dot_size)
    axes.scatter(x['coap'], y['coap'], label=coap_label, color=coap_color, alpha=alpha, s=dot_size)

    axes.legend(loc=label_loc, fontsize=legend_size, title_fontsize=legend_title_size)
    axes.set_title("Publisher CPU usage\nwith respect to " + ld_title, fontsize=title_size)
    axes.set_xlabel(ld_xlabel, fontsize=label_size, labelpad=labelpad)
    axes.set_ylabel('Relative CPU time per publication', fontsize=label_size, labelpad=labelpad)
    
    plt.xticks(fontsize=xticks_size)
    plt.yticks(fontsize=yticks_size)
    plt.locator_params(axis='x', nbins=7)
    axes.yaxis.set_major_formatter(FormatStrFormatter('%2d'))
    axes.xaxis.set_minor_locator(AutoMinorLocator())
    axes.yaxis.set_minor_locator(AutoMinorLocator())
    axes.tick_params(which='both', width=2)
    axes.tick_params(which='major', length=7)
    axes.tick_params(which='minor', length=4)
    plt.savefig(os.path.join(savedir, d, 'perf_pub_rel.pdf'))



    var = 'perf_srv_rel'
    x,y = get_figure_stats(results, var)
    y['wt_z'] = [x/y['wt_z'][0] for x in y['wt_z']]
    y['wt'] = [x/y['wt'][0] for x in y['wt']]
    y['mqtt'] = [x/y['mqtt'][0]for x in y['mqtt']]
    y['coap'] = [x/y['coap'][0] for x in y['coap']]
    figure = plt.figure()
    figure.set_size_inches(figure_size)
    axes = figure.add_subplot(1,1,1)
    x_smooth,y_smooth = get_smooth_line(x['wt_z'], y['wt_z'])
    axes.plot(x_smooth, y_smooth, color=wt_z_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['wt'], y['wt'])
    axes.plot(x_smooth, y_smooth, color=wt_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['mqtt'], y['mqtt'])
    axes.plot(x_smooth, y_smooth, color=mqtt_color, alpha=alpha, linewidth=linewidth)
    x_smooth,y_smooth = get_smooth_line(x['coap'], y['coap'])
    axes.plot(x_smooth, y_smooth, color=coap_color, alpha=alpha, linewidth=linewidth)
    axes.scatter(x['wt_z'], y['wt_z'], label=wt_z_label, color=wt_z_color, alpha=alpha, s=dot_size)
    axes.scatter(x['wt'], y['wt'], label=wt_label, color=wt_color, alpha=alpha, s=dot_size)
    axes.scatter(x['mqtt'], y['mqtt'], label=mqtt_label, color=mqtt_color, alpha=alpha, s=dot_size)
    axes.scatter(x['coap'], y['coap'], label=coap_label, color=coap_color, alpha=alpha, s=dot_size)

    axes.legend(loc=label_loc, fontsize=legend_size, title_fontsize=legend_title_size)
    axes.set_title("Server/Broker CPU usage\nwith respect to " + ld_title, fontsize=title_size)
    axes.set_xlabel(ld_xlabel, fontsize=label_size, labelpad=labelpad)
    axes.set_ylabel('Relative CPU time per publication', fontsize=label_size, labelpad=labelpad)
    
    plt.xticks(fontsize=xticks_size)
    plt.yticks(fontsize=yticks_size)
    plt.locator_params(axis='x', nbins=7)
    axes.yaxis.set_major_formatter(FormatStrFormatter('%.1f'))
    axes.xaxis.set_minor_locator(AutoMinorLocator())
    axes.yaxis.set_minor_locator(AutoMinorLocator())
    axes.tick_params(which='both', width=2)
    axes.tick_params(which='major', length=7)
    axes.tick_params(which='minor', length=4)
    plt.savefig(os.path.join(savedir, d, 'perf_srv_rel.pdf'))


plt.show(block=False)
atexit.register(plt.show, block=True)