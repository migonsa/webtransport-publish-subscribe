import pyshark, argparse


def generate_pcap_csv(pcapfile, outfile):
    #print("Generating pcap's CSV...")
    capture = pyshark.FileCapture(pcapfile)
    with open(outfile, "w") as file:
        for packet in capture:
            try:
                file.write("%s, %s, %s, %s\n" % (packet.frame_info.time_epoch.replace('.', ''), packet.ip.src, packet.ip.dst, packet.length))
            except Exception as e:
                pass
    capture.close()
    #print("DONE!\n")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="PCAP CSV GENERATOR")

    parser.add_argument(
        "server",
        type=str,
        metavar="wt_z, wt, coap, mqtt",
        choices=["wt_z", "wt", "coap", "mqtt"],
        help="type of server",
    )

    args = parser.parse_args()

    generate_pcap_csv(args.server)