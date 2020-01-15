# -*- coding: utf-8 -*-
import sys
import socket
from socket import error as socket_error
import time
from data_import import read_utterance

hosts = read_utterance("../network/commu_data.csv")

if __name__ == '__main__':
    clients = []

    for clientdata in hosts:
        host = clientdata["host"]
        port = clientdata["port"]
        try:
            for res in socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM):
                af, socktype, proto, canonname, sa = res
                try:
                    sock = socket.socket(af, socktype, proto)
                    clients.append(sock)
                except OSError as msg:
                    sock = None
                    continue
                try:
                    sock.connect(sa)
                except OSError as msg:
                    sock.close()
                    sock = None
                    continue
                break

        except socket_error as serr:
            print("Connection:" + str(host) + ":" + str(port) + " refused.")
            sys.exit()

    for c in clients:
        print(c)

    while(True):
        time.sleep(0.01)
        path_command = '../tempdata/commands_to_be_sent.txt'
        with open(path_command, mode='r') as f:
            first_line = f.readline()

        com = first_line[:-1].split(';')  # コミューの番号、命令の内容
        # print(com)
        if len(com) > 1:
            which_commu = int(com[0])
            client = clients[which_commu]
            host = hosts[which_commu]["host"]
            command = com[1] + "\n"
            print("SEND To: "+host+" command: " + str(com))
            client.send(command.encode('utf-8'))

            if len(com) >= 3:
                print("sleep: " + com[2])
                sleeplen = float(com[2])
                time.sleep(sleeplen)

            with open(path_command, "r+") as f:  # 一行目消去
                new_f = f.readlines()
                f.seek(0)
                ln = 0

                for line in new_f:
                    if ln > 0:
                        f.write(line)
                    ln += 1
                f.truncate()