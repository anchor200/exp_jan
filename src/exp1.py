import sys
import time
import socket
import csv
from data_import import read_utterance
import threading
import random
import datetime
from collections import deque

class DialogManager:
    def __init__(self, host, port, TOPIC_ID=0, PARTICIPANTS = 4):
        self.PARTICIPANTS = PARTICIPANTS
        self.TOPIC_ID = TOPIC_ID
        self.DEFAULT_PACE = 6

        self.variables_prepare()
        self.socket_and_thread_start(host, port)

    def variables_prepare(self):
        self.opn_pathes = []
        self.path_command = '../tempdata/commands_to_be_sent.txt'
        s = ""
        with open(self.path_command, mode='w', encoding="utf-8") as f:
            f.write(s)
        # 送るのが待たれているコマンドを記録するファイル

    def socket_and_thread_start(self, host, port):
        self.serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, True)
        self.clients = []
        self.serversocket.bind((host, port))
        self.serversocket.listen(128)

        # サーバソケットを渡してワーカースレッドを起動する
        NUMBER_OF_THREADS = 10
        for _ in range(NUMBER_OF_THREADS):
            self.thread = threading.Thread(target=self.worker_thread, args=(self.serversocket,))
            self.thread.daemon = True
            self.thread.start()

        # command_to_sendの命令がすべて実行されたかどうかを記録する
        # 一定行以上あるなら選択できないようにする
        # self.thread_for_speech_end_check = threading.Thread(target=self.operation_waiting_check)
        # self.thread_for_speech_end_check.start()

        while True:
            # メインスレッドは遊ばせておく (ハンドラを処理させても構わない)
            time.sleep(1)

    def sender_detection(self, client_address, client_port):
        j = 0
        sender_of_the_message = j
        for i in self.clients:
            if (client_address, client_port) == i[1]:
                sender_of_the_message = j
                break
            j += 1
        """for i in self.clients:
            if client_address == i[1][0]:
                sender_of_the_message = j
                break
            j += 1"""

        return sender_of_the_message

    def opn_input_save(self, mes):
        if "%" in mes:
            temp = mes.split("%")[-1].split(":")
            opn_to_save = temp[0] + "," + temp[1]

            ID = mes.split("%")[1]
            tempPath = self.opn_pathes[0][0]
            for can in self.opn_pathes:
                if can[1] == ID:
                    tempPath = can[0]

            with open(tempPath, mode='a', encoding="utf-8") as f:
                f.write(opn_to_save)

    def command_generation(self, mes):
        # print(mes)
        if "<Command>" in mes:
            temp1 = mes.split("<Command>:")
            for temp2 in temp1:
                temp = temp2.split(",")
                if len(temp) >= 3:
                    command = ""
                    if temp[0] == "A":
                        command += "0;"
                    elif temp[0] == "B":
                        command += "1;"
                    elif temp[0] == "C":
                        command += "2;"
                    elif temp[0] == "D":
                        command += "3;"
                    command += temp[2]

                    with open(self.path_command, mode='a', encoding="utf-8") as f:
                        f.write(command)

    def main_claim_saver(self, mes):
        if "<MainClaim>" in mes:
            mes = mes.split("\n")[0]
            path_mc = '../tempdata/main_claims.txt'
            with open(path_mc, mode='w', encoding="utf-8") as f:
                f.write(mes)

    def worker_thread(self, none):
        """クライアントとの接続を処理するハンドラ"""
        self.next_speaker = 0
        while True:
            # クライアントからの接続を待ち受ける (接続されるまでブロックする)
            # ワーカスレッド同士でクライアントからの接続を奪い合う
            clientsocket, (client_address, client_port) = self.serversocket.accept()

            message = clientsocket.recv(1024)
            raw_mes = message.decode('utf-8')
            ID = "Z"
            NAME = "Hiroshi"
            if "<ID>" in raw_mes:
                ID = raw_mes.split(":")[-1].split(",")[0]
                NAME = raw_mes.split(":")[-1].split(",")[1]
                ROBO = raw_mes.split(":")[-1].split(",")[2]
                print(ID, NAME)

            self.clients.append((clientsocket, (client_address, client_port), ID, NAME))
            todaydetail = datetime.datetime.today()
            opn_path = '../tempdata/OpnInputRef' + ID + NAME + "_" + str(todaydetail.strftime("%Y%m%d_%H%M%S")) + '.txt'
            opn_path = opn_path.replace("\n", "")
            s = "<ID>," + ID + "," + NAME + "," + ROBO
            with open(opn_path, mode='w', encoding="utf-8") as f:
                f.write(s)

            self.opn_pathes.append([opn_path, ID, NAME])

            clientsocket.sendto(("you are <ID> :" + ID + "," + NAME).encode('utf-8'), (client_address, client_port))
            print('New client: {0}:{1}'.format(client_address, client_port))
            # クライアントは0からカウント　ユーザ0、ユーザ1、ユーザ2
            while True:
                try:
                    message = clientsocket.recv(1024)
                    raw_mes = message.decode('utf-8')

                    if raw_mes != "":
                        print("recv:" + raw_mes)

                        sender = self.sender_detection(client_address, client_port)
                        self.main_claim_saver(raw_mes)
                        self.opn_input_save(raw_mes)
                        self.command_generation(raw_mes)

                except OSError:
                    break

            clientsocket.close()
            print('Bye-Bye: {0}:{1}'.format(client_address, client_port))
            sender = self.sender_detection(client_address, client_port)
            del self.clients[sender]  # 接続が切れたらクライアントリストから削除


if __name__ == '__main__':
    def_port = 50000
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('192.168.100.1', 80))
    ip = s.getsockname()[0]
    print("waiting at :" + ip + ":" + str(def_port))
    # s = DialogManager(ip, def_port, TOPIC_ID=0)
    s = DialogManager('127.0.0.1', 5000, TOPIC_ID=0)