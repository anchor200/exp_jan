import sys
import time
import socket
import csv
from data_import import read_utterance
import threading
import random
import datetime
from collections import deque
from collections import OrderedDict
import re
import glob
import os
from pykakasi import kakasi

class DialogManager:
    def __init__(self, host, port, TOPIC="LOVE", PARTICIPANTS = 4):
        self.PARTICIPANTS = PARTICIPANTS
        self.TOPIC = TOPIC
        self.DEFAULT_PACE = 6
        self.ID = "Z"

        self.variables_prepare()
        self.constatns_prepare()
        self.gestures_and_utterance_preset()
        self.timer = time.perf_counter()

        self.kakasi = kakasi()
        self.kakasi.setMode("J", "H")
        self.converter = self.kakasi.getConverter()

        self.socket_and_thread_start(host, port)

    def constatns_prepare(self):
        path_bc = '../peripheral/backchanneling.txt'
        with open(path_bc, encoding="utf-8") as f:
            self.Aiduchi = [s.strip() for s in f.readlines()]

        self.Names = []
        self.Opinions = []
        partcipants = [chr(i) for i in range(65, 65+self.PARTICIPANTS)]
        for p in partcipants:
            path = "../tempdata/OpnInputRef" + str(p) + "*.txt"
            l = sorted(glob.glob(path), key=os.path.getmtime)
            with open(l[-1], encoding="utf-8") as f:
                l_strip = [s.strip() for s in f.readlines()]
            print (l_strip)

            od = OrderedDict()
            od["<ID>"] = l_strip[0].split(",")[1]
            od["<YourName" + l_strip[0].split(",")[1] + ">"] = l_strip[0].split(",")[2]
            od["<RoboName" + l_strip[0].split(",")[1] + ">"] = l_strip[0].split(",")[3]
            self.Names.append([l_strip[0].split(",")[1], od])
            od = OrderedDict()
            for li in l_strip[1:]:
                n = li.split(",")
                od[n[0]] = n[1]
            self.Opinions.append([l_strip[0].split(",")[1], od])
        print(self.Names, self.Opinions)

        self.MainClaims = []
        path_mc = '../tempdata/main_claims.txt'
        with open(path_mc, encoding="utf-8") as f:
            l_strip = [s.strip() for s in f.readlines()][0]
        keys = l_strip.split(":")[-1].split(";")[0].split(",")
        body = l_strip.split(";")[1:]
        for content in body:
            print(content)
            dev_by_keys = content.split(",")
            od = OrderedDict()
            for i in range(len(keys)):
                od[keys[i]] = dev_by_keys[i]
            self.MainClaims.append(od)
        print(self.MainClaims)

        self.dialogue_transcript = []  # 発話の台本
        partcipants = [chr(i) for i in range(65, 65 + self.PARTICIPANTS)]
        for p in partcipants:
            srcA = read_utterance("../transcripts/PRESET/Branch" + p + ".csv")
            self.dialogue_transcript.append(srcA)
        self.contol_code = read_utterance("../transcripts/PRESET/ControlCode.csv")

    def variables_prepare(self):
        self.next_speech_holder = "0000"
        self.kakasi = kakasi()
        self.kakasi.setMode("J", "H")
        self.converter = self.kakasi.getConverter()

        self.toBegin = 999  # 全員が始めるボタンを押すまで待つ
        self.p_on_focus = 0  # 誰がメインの話者か(0=A)

        self.opn_relation = []  # それぞれの意見に対するそれぞれの反応
        for i in range(self.PARTICIPANTS):
            tempopn = []
            for j in range(self.PARTICIPANTS):
                tempopn.append("<Neutral>")  # <Neutral> <Agree> <DisAgree>の三つある
            self.opn_relation.append(tempopn)

        self.path_command = '../tempdata/commands_to_be_sent.txt'
        s = ""
        with open(self.path_command, mode='w', encoding="utf-8") as f:
            f.write(s)
        # 送るのが待たれているコマンドを記録するファイル

    def gestures_and_utterance_preset(self):
        self.gesture_furikaeri = "furikaeri"
        self.gesture_furikaeri_kaijo = "furikaeri_kaijo"
        self.gesture_front = "/look M 0 300 300"
        self.gestures_on_short_utterance = ["short_utterance_R", "short_utterance_L"]
        self.gestures_on_long_utterance = ["long_utterance", "long_utterance_3", "long_utterance_4"]
        self.gestures_on_agreement = ["nod1", "nod2", "nod3"]
        self.gestures_on_opposition = ["kubihuri", "kubikashigeL", "kubikashigeR"]
        # self.gestures_on_raise_hand = ["raisehand_L_first", "raisehand_R_fisrt"]
        self.gestures_on_raise_hand = ["short_utterance_R", "short_utterance_L"]
        self.utterance_on_raise_hand = ["僕からいいかな", "えっと", "はい", "話していい？", "話したいです", "うーんと", "なんというか、その", "いろいろあるけど、えっと"]
        self.gaze_on_listening = [["/look M 0 300 300", "/look M -200 300 300", "/look M 0 300 300", "/look M 200 300 300"],
                                  ["/look M 200 300 300", "/look M 0 300 300", "/look M -200 300 300", "/look M 0 300 300"],
                                  ["/look M 0 300 300", "/look M 200 300 300", "/look M 0 300 300", "/look M -200 300 300"],
                                  ["/look M -200 300 300", "/look M 0 300 300", "/look M 200 300 300", "/look M 0 300 300"]]

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

    def wait_duration_calculation(self, utterance):
        temp = len(self.converter.do(utterance))
        return temp / 5 + 2  # unity側の、押してから選択肢が消えるまでの時間との兼ね合いがある。

    def command_generation(self, mes, operation):
        # print(mes)
        who = -1
        if "<Command>" in mes:
            temp1 = mes.split("<Command>:")
            for temp2 in temp1:
                temp = temp2.split(",")
                if len(temp) >= 3:
                    command = ""
                    if temp[0] == "A":
                        who = 0
                        gaze = self.gaze_on_listening[0]
                    elif temp[0] == "B":
                        who = 1
                        gaze = self.gaze_on_listening[1]
                    elif temp[0] == "C":
                        who = 2
                        gaze = self.gaze_on_listening[2]
                    elif temp[0] == "D":
                        who = 3
                        gaze = self.gaze_on_listening[3]

                    if who >= 0:
                        for i in range(self.PARTICIPANTS):
                            if not i == who:
                                gaze = self.gaze_on_listening[who][i]
                                command = str(i) + ";" + gaze + ";" + "0\n"
                                with open(self.path_command, mode='a', encoding="utf-8") as f:
                                    f.write(command)

                    command += str(who) + ";" + "/say " + temp[2]
                    waittime = self.wait_duration_calculation(temp[2])

                    if re.search(r'<LookNingenAll>|<LookAllKaijo>', operation):
                        command += ";" + str(waittime)
                        command += "\n"
                        with open(self.path_command, mode='a', encoding="utf-8") as f:
                            f.write(command)
                        self.look_ningen(operation, who)
                    else:  # 振り向き等があったかどうか
                        gesture = ""
                        if operation == "<LookNingen>":
                            gesture = self.gesture_furikaeri
                        elif operation == "<LookKaijo>":
                            gesture = self.gesture_furikaeri_kaijo
                        elif temp[3] == "":
                            if waittime < 8.0:
                                gesture = random.choice(self.gestures_on_short_utterance)
                            else:
                                gesture = random.choice(self.gestures_on_long_utterance)
                        elif temp[3] == "<Positive>":
                            gesture = random.choice(self.gestures_on_agreement)
                        elif temp[3] == "<Negative>":
                            gesture = random.choice(self.gestures_on_opposition)
                        command += " /gesture " + gesture
                        command += ";" + str(waittime)
                        command += "\n"
                        with open(self.path_command, mode='a', encoding="utf-8") as f:
                            f.write(command)
        return waittime

    def id_search(self, id):  # 現在の台本、あいづち、個tントローラー全部見る
        for line in self.dialogue_transcript[self.p_on_focus]:
            if id == line["発話ID"]:
                return line
        for line in self.contol_code:
            if id == line["発話ID"]:
                print(line)
                return line

    def designate_next_line(self, next_list, designator, who_num):  # next listはIDの一覧  # whoは直前の発話者の番号
        line_list = []
        for id in next_list:
            line_list.append(self.id_search(id))

        if designator == "":
            return line_list
        elif designator == "<Holding>":
            return line_list
        elif designator == "<NingenDiscuss>":
            return line_list
        elif designator == "<PrefDiv>":  # 賛否が関係ある時は、0賛成1中立2反対  遠い意見は削除する
            if self.opn_relation[self.p_on_focus][who_num] == "<Agree>":
                del line_list[2]
            elif self.opn_relation[self.p_on_focus][who_num] == "<DisAgree>":
                del line_list[0]
            return line_list

        return []

    def preference_register(self, operation, who_num):
        if re.search(r'<Agree>|<Neutral>|<DisAgree>' ,operation):
            self.opn_relation[self.p_on_focus][who_num] = operation

    def look_ningen(self, operation, who_num):
        command = ""
        diddid = False
        if operation == "<LookNingen>":
            print(operation)
            command = str(who_num) + ";/gesture " + self.gesture_furikaeri + ";0\n"
            diddid = True
        elif operation == "<LookKaijo>":
            print(operation)
            command = str(who_num) + ";/gesture " + self.gesture_furikaeri_kaijo + ";0\n"
            command += str(who_num) + ";" + self.gesture_front + ";0\n"
            diddid = True
        elif operation == "<LookNingenAll>":
            print(operation)
            for i in range(self.PARTICIPANTS):
                command = str(i) + ";/gesture " + self.gesture_furikaeri + ";0\n"
            diddid = True
        elif operation == "<LookAllKaijo>":
            print(operation)
            for i in range(self.PARTICIPANTS):
                command = str(i) + ";/gesture " + self.gesture_furikaeri_kaijo + ";0\n"
                command += str(i) + ";" + self.gesture_front + ";0\n"
            diddid = True

        with open(self.path_command, mode='a', encoding="utf-8") as f:
            f.write(command)
        return  diddid

    def generate_choice_sender(self, speech):
        sender = "<Choice>:"
        next = "Z"
        aiduchiIn = OrderedDict()
        i = 0
        mark = -1
        for detail in speech:
            if "<Aiduchi>" in detail["表示"]:
                mark = i
            i += 1
        if mark >= 0:
            aiduchiIn = speech.pop(mark)

            aiduchis = random.sample(self.Aiduchi, 3)
            print(aiduchis)
            for aiduchi in aiduchis:
                text = aiduchi.split(",")[0]
                attitude = aiduchi.split(",")[1]
                sender += aiduchiIn["発話ID"] + "," + aiduchiIn["発話者"] + "," + text + "," + text + "," + attitude + ";"

                next = aiduchiIn["発話者"]

        for detail in speech:
            try:
                sender += detail["発話ID"] + "," + detail["発話者"] + "," +  detail["表示"] + "," +  detail["発話"] + "," + detail["態度"] + ";"
            except TypeError:
                sender += detail["発話ID"] + "," + detail["発話者"] + "," + detail["表示"] + "," + detail["発話"] + ";"
                next = detail["発話者"]
        return sender[:-1], next

    def choice_generation(self, mes):
      if "<Command>" in mes:
            who = mes.split(":")[-1].split(",")[0]
            who_num = 0
            if who == "A":
                who_num = 0
            elif who == "B":
                who_num = 1
            elif who == "C":
                who_num = 2
            elif who == "D":
                who_num = 3
            speech_id = mes.split(":")[-1].split(",")[1]
            temp_line = self.id_search(speech_id)
            new_list = temp_line["次の発話の候補"].split(";")
            designator = temp_line["次の発話の決め方"]
            operation = temp_line["特殊な操作"]
            self.preference_register(operation, who_num)  # この後には何らかの発話をさせるかもここで戻らせる
            new_list = self.designate_next_line(new_list, designator, who_num)

            if designator == "<Begin>":  # スタートが来た場合は先頭に送る   ここ大事！！！！
                self.toBegin += 1
                if self.toBegin < self.PARTICIPANTS:
                    return
                self.p_on_focus = 0
                new_list = [self.id_search(self.dialogue_transcript[self.p_on_focus][0]["発話ID"])]

            if designator == "<Transition>":
                self.p_on_focus += 1
                new_list = [self.id_search(self.dialogue_transcript[self.p_on_focus][0]["発話ID"])]
            elif designator == "<Terminate>":
                time.sleep(5)
                end_mes = "<Choice>:0001," + self.ID + ",@おわり,みんな、ありがとう,"
                for c in self.clients:
                    c[0].sendto(end_mes.encode('utf-8'), c[1])
                return
            elif designator == "<NingenDiscuss>":
                self.next_speech_holder = new_list
                print("saved:")
                print(new_list)
                holding = "<Choice>:0002," + self.ID + ",@話す,,"
                self.timer = time.perf_counter()
                for c in self.clients:
                    c[0].sendto(holding.encode('utf-8'), c[1])

                return
            elif designator == "<Holding>":
                print(time.perf_counter() - self.timer)
                if time.perf_counter() - self.timer > 15:
                    new_list = self.next_speech_holder
                else:
                    time.sleep(10)
                    pass

            waiting_time = self.command_generation(mes, operation)
            """if who_speak >= 0:
                for i in range(self.PARTICIPANTS):
                    gaze = self.gaze_on_listening[who_speak][i]
                    command = str(i) + ";" + gaze + ";" + "0\n"
                    with open(self.path_command, mode='a', encoding="utf-8") as f:
                        f.write(command)"""




            line_to_send, next_speaker = self.generate_choice_sender(new_list)
            print("send" + line_to_send)

            t = threading.Timer(waiting_time, self.send_choice, args=[line_to_send, next_speaker])
            t.start()

            # あいづちのときはまた別

    def fix_transcript(self, line):
        print(line)
        for names in self.Names:
            dic = names[1]
            keys = dic.keys()
            for key in keys:
                line = line.replace(key, dic[key])
        opinions = self.Opinions[self.p_on_focus]
        dic = opinions[1]
        keys = dic.keys()
        for key in keys:
            line = line.replace(key, dic[key])


        claims = self.MainClaims[self.p_on_focus]
        keys = claims.keys()
        for key in keys:
            line = line.replace(key, claims[key])
        print(line)
        return  line

    def send_choice(self, line_to_send, next_speaker):
        line_to_send = self.fix_transcript(line_to_send)
        for c in self.clients:
            if c[2] == next_speaker or True:
                c[0].sendto(line_to_send.encode('utf-8'), c[1])


    def worker_thread(self, none):
        """クライアントとの接続を処理するハンドラ"""
        self.next_speaker = 0
        while True:
            # クライアントからの接続を待ち受ける (接続されるまでブロックする)
            # ワーカスレッド同士でクライアントからの接続を奪い合う
            clientsocket, (client_address, client_port) = self.serversocket.accept()

            message = clientsocket.recv(1024)
            raw_mes = message.decode('utf-8')
            self.ID = "Z"
            NAME = "Hiroshi"
            if "<ID>" in raw_mes:
                self.ID = raw_mes.split(":")[-1].split(",")[0]
                NAME = raw_mes.split(":")[-1].split(",")[-1]
                print(self.ID, NAME)

            self.clients.append((clientsocket, (client_address, client_port), self.ID))

            # clientsocket.sendto(("you are <ID> :" + ID + "," + NAME).encode('utf-8'), (client_address, client_port))
            time.sleep(1)
            clientsocket.sendto(("<Choice>:0000," + self.ID + ",@はじめる,よろしく,").encode('utf-8'), (client_address, client_port))

            print('New client: {0}:{1}'.format(client_address, client_port))
            # クライアントは0からカウント　ユーザ0、ユーザ1、ユーザ2
            while True:
                try:
                    message = clientsocket.recv(1024)
                    raw_mes = message.decode('utf-8')

                    if raw_mes != "":
                        print("recv:" + raw_mes)
                        # sender = self.sender_detection(client_address, client_port)

                        self.choice_generation(raw_mes)

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
    s = DialogManager('127.0.0.1', 5000, TOPIC=0)