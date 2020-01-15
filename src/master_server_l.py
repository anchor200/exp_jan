import sys
import time
import socket
import csv
from data_import import read_utterance
import threading
import random
from pykakasi import kakasi
import datetime
from collections import deque

class DialogManager:
    def __init__(self, host, port, TOPIC_ID=0, PARTICIPANTS = 4):
        self.PARTICIPANTS = PARTICIPANTS
        self.TOPIC_ID = TOPIC_ID
        self.DEFAULT_PACE = 6

        self.data_input()
        self.files_and_variables_preparation()
        self.kakasi = kakasi()
        self.kakasi.setMode("J", "H")
        self.converter = self.kakasi.getConverter()

        self.socket_and_thread_start(host, port)

    def files_and_variables_preparation(self):
        # 定数
        self.koushin = "koushin"
        self.hatsuwa = "hatsuwa"
        self.conjunction = "conjunction"
        self.opinion = "opinion"
        self.transition = "transition"
        self.backchanneling = "backchanneling"
        self.facilitation = "facilitation"
        self.gestures_and_utterance_preset()
        self.q = 0
        self.next_speaker = 0
        self.q_sequence = [self.q]
        self.PACE = self.DEFAULT_PACE
        self.length_of_latest_utterance = 0
        self.latest_operation_time = deque([0,0,time.perf_counter()], maxlen=3)
        self.marked_utterance = ["", "", ""]

        self.turns_same_q = 0  # おなじqでどれだけのターンが持ったか
        self.log_by_p = [[[], []], [[], []], [[], []], [[], []]]
        todaydetail = datetime.datetime.today()
        self.speaker_log = []
        # 各参加者の発話履歴と禁止コマンドの記録 [発話履歴],[禁止コマンド]
        self.path_log = '../tempdata/dialogue_log_' + str(todaydetail.strftime("%Y%m%d_%H%M%S")) + '.txt'
        s = ""
        with open(self.path_log, mode='w') as f:
            f.write(s)
        # シナリオのログの新規作成
        self.path_command = '../tempdata/commands_to_be_sent.txt'
        s = ""
        with open(self.path_command, mode='w') as f:
            f.write(s)
        # 送るのが待たれているコマンドを記録するファイル

        # 始まった時点ではみんな正面を向いている！
        command = str(self.PARTICIPANTS - 1) + ";" + "/aitalk-pitch 0.7" + "\n"
        with open(self.path_command, mode='a') as f:
            f.write(command)

        for j in range(self.PARTICIPANTS):
            command = str(j) + ";" + "/gesture init" + "\n"
            with open(self.path_command, mode='a') as f:
                f.write(command)
            command = str(j) + ";" + "/look M 0 300 300" + "\n"
            with open(self.path_command, mode='a') as f:
                f.write(command)
            command = str(j) + ";" + "/aitalk-speed 1.1" + "\n"
            with open(self.path_command, mode='a') as f:
                f.write(command)
        time.sleep(1)

    def data_input(self):
        self.dialogue_structure = read_utterance("../questions/TOPIC_" + str(self.TOPIC_ID) + "/dialogue_structure.csv")
        self.utterance_database = []
        for x in self.dialogue_structure:
            temp = read_utterance("../questions/TOPIC_" + str(self.TOPIC_ID) + "/q_" + str(x["q_num"]) + ".csv")
            self.utterance_database.append(temp)
        self.ending_utterance = read_utterance("../questions/TOPIC_" + str(self.TOPIC_ID) + "/ending.csv")

        self.backchanneling_database = read_utterance("../peripheral/backchanneling.csv")
        self.facilitation_database = read_utterance("../peripheral/facilitation.csv")
        self.pass_to_others_database = read_utterance("../peripheral/pass_to_others.csv")
        self.conjunction_database = []
        self.conjunction_classes = ["0_junsetsu", "1_gyakusetsu", "2_heiretsu", "3_taichi", "4_tenkan", "5_matome", "6_kyomu"]
        for x in self.conjunction_classes:
            temp = read_utterance("../peripheral/" + str(x) + ".csv")
            self.conjunction_database.append(temp)

    def gestures_and_utterance_preset(self):
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
        self.users = []
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
        self.thread_for_speech_end_check = threading.Thread(target=self.operation_waiting_check)
        self.thread_for_speech_end_check.start()

        while True:
            # メインスレッドは遊ばせておく (ハンドラを処理させても構わない)
            time.sleep(1)

    def operation_waiting_check(self):
        # ここのループを回してる関係でつなぎなおしができなくなってる
        previous = 0
        while True:
            time.sleep(0.1)
            if self.length_of_latest_utterance > previous:  # 新しい入力があって、発話終了見込みが伸びた
                for c in self.clients:
                    print("------operation_blocking")
                    c[0].sendto("/operation_blocking\n".encode('utf-8'), c[1])

            if self.length_of_latest_utterance > 0:
                self.length_of_latest_utterance -= 0.1
            if self.length_of_latest_utterance <= 0:
                if self.length_of_latest_utterance != previous:
                    self.length_of_latest_utterance = 0
                    for c in self.clients:
                        print("------operation_waiting")
                        c[0].sendto("/operation_waiting\n".encode('utf-8'), c[1])

            previous = self.length_of_latest_utterance

    def command_check(self):
        are_command_remaining = False
        while True:
            with open(self.path_command, mode='r') as f:
                l = f.readlines()
            if len(l) > 5:
                are_command_remaining = True
            if are_command_remaining and len(l) <= 5:
                are_command_remaining = False
                for c in self.clients:
                    # コマンドが５行以下になった時に、送ってもいいよと端末に送る（コマンドが溜まってしまったときにたまりすぎを抑止するため）
                    c[0].sendto("operation_waiting".encode('utf-8'), c[1])
            time.sleep(0.5)

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

    def delete_opinion_from_v(self, id):
        print("start deletion")
        """j = 0
        for x in self.utterance_database[self.q]:
            if x["id"] == id:
                break
            j += 1
        if j < len(self.utterance_database[self.q]):
            del self.utterance_database[self.q][j]"""
        for q in range(len(self.dialogue_structure)):
            j = 0
            for y in self.utterance_database[q]:
                if y["id"] == id:
                    break
                j += 1
            if j < len(self.utterance_database[q]):
                print("deleted", self.utterance_database[q][j])
                del self.utterance_database[q][j]

        # print(id, self.utterance_database[self.q])
    # 発話に選ばれたものがvの中にあれば消去する

    def id_search(self, id):
        id = id.replace("\n", "")
        print("searching for " + id)
        try:
            if id[0] == "C":
                utterance_type = self.conjunction
                conjunction_class = int(id[1])
                for x in self.conjunction_database[conjunction_class]:
                    if x["id"] == id:
                        return utterance_type, x
            elif id[0] == "B":
                utterance_type = self.backchanneling
                for x in self.backchanneling_database:
                    if x["id"] == id:
                        return utterance_type, x
            elif id[0] == "F":
                utterance_type = self.facilitation
                for x in self.facilitation_database:
                    if x["id"] == id:
                        return utterance_type, x
            elif id[0] == "E":
                utterance_type = self.opinion
                for x in self.ending_utterance:
                    if x["id"] == id:
                        return utterance_type, x
            elif id[0] == "G":
                utterance_type = self.facilitation
                for x in self.pass_to_others_database:
                    if x["id"] == id:
                        return utterance_type, x

            else:
                utterance_type = self.opinion
                print("searching in utterance database " + str(self.q))
                for x in self.utterance_database[self.q]:
                    print(x["id"], id)
                    if x["id"] == id:
                        return utterance_type, x
                which_q = int(id[0])
                for x in self.utterance_database[which_q]:
                    print(x["id"], id)
                    if x["id"] == id:
                        return utterance_type, x
                which_q = int(id[:2])
                if which_q < len(self.utterance_database):
                    for x in self.utterance_database[which_q]:
                        print(x["id"], id)
                        if x["id"] == id:
                            return utterance_type, x


        except KeyError:
            return "error", self.backchanneling_database[-1]
        except IndexError:
            return "error", self.backchanneling_database[-1]

        return "error", self.backchanneling_database[-1]
    # IDから辞書の要素をとってくる return [どんな種類の発話か], 辞書の要素としての発話

    def wait_duration_calculation(self, utterance):
        temp = len(self.converter.do(utterance))
        return temp / 4 + 1

    def write_command(self, sender, conjunction, utterance_type, utterance):
        print([conjunction["class"], utterance_type])
        if utterance_type == "error":
            return "はじまり"
        # utteranceは辞書の要素の型のリスト（[接続詞、発言]）
        # コミューに送るコマンドを（三体分）生成する
        command = ""

        # 発言するものが手を挙げる(意見の場合で、かつ接続詞なしで発話する場合)
        if self.q == 0 and utterance_type != self.backchanneling:
            print("introduction")
            command = str(sender) + ";" + "/say " + utterance["utterance"] + "[EOF]" + \
                      " /gesture " + random.choice(self.gestures_on_short_utterance)
            utterance_length = 2
            self.length_of_latest_utterance += utterance_length
            command += ";" + str(utterance_length) + "\n"
            with open(self.path_command, mode='a') as f:
                f.write(command)
            with open(self.path_log, mode='a') as f:
                f.write(str(time.perf_counter()) + "|" + command)
            gaze = self.gaze_on_listening[sender]
            for j in range(len(gaze)):
                command = str(j) + ";" + gaze[j] + "\n"
                with open(self.path_command, mode='a') as f:
                    f.write(command)
                with open(self.path_log, mode='a') as f:
                    f.write(str(time.perf_counter()) + "|" + command)
            return utterance["utterance"]

        if utterance_type == self.opinion and self.q != 0:
            u_temp = random.choice(["うーんと、", "えっと、", "その、", "えーっと、"])

            ryuho = ""
            if utterance["id"] in self.log_by_p[sender][1]:
                ryuho += random.choice(["あまり一貫していないかもしれないけど、", "さっきとは違う意見かもしれないけど、", "改めて考えると、", "さっきとは変わるけど、", "いままでとはちょっと矛盾するんだけど、", "はっきりとはまとまってないけど、", "さっき言ったのとは違うけど、"])
            """if utterance["control"] != self.transition and len(utterance["utterance"]) > 19:
                u_temp = random.choice(self.utterance_on_raise_hand)"""
            command = str(sender) + ";" +\
                       "/say " + u_temp + ryuho + "[EOF]"
            utterance_length = 1# self.wait_duration_calculation(u_temp)
            self.length_of_latest_utterance += utterance_length
            command += ";" + str(utterance_length) + "\n"
            with open(self.path_command, mode='a') as f:
                f.write(command)
            with open(self.path_log, mode='a') as f:
                f.write(str(time.perf_counter()) + "|" + command)
            # 手が挙がったら、発言するもの以外は発言するものを見る
            gaze = self.gaze_on_listening[sender]
            for j in range(len(gaze)):
                command = str(j) + ";" + gaze[j] + "\n"
                with open(self.path_command, mode='a') as f:
                    f.write(command)
                with open(self.path_log, mode='a') as f:
                    f.write(str(time.perf_counter()) + "|" + command)

            # 発話本体
            utterance_temp = conjunction["buffer"] + conjunction["label"] + "、" + utterance["utterance"]
            if self.is_long_utterance(utterance_temp):
                command = str(sender) + ";" + "/say " + utterance_temp + "[EOF]" +\
                    " /gesture " + random.choice(self.gestures_on_long_utterance)
            else:
                command = str(sender) + ";" + "/say " + utterance_temp + "[EOF]" + \
                          " /gesture " + random.choice(self.gestures_on_short_utterance)
            utterance_length = self.wait_duration_calculation(utterance_temp)
            self.length_of_latest_utterance += utterance_length
            command += ";" + str(utterance_length) + "\n"
            with open(self.path_command, mode='a') as f:
                f.write(command)
            with open(self.path_log, mode='a') as f:
                f.write(str(time.perf_counter()) + "|" + command)
            # 正面に向き直る
            """for j in range(self.PARTICIPANTS):
                command = str(j) + ";" + "/look M 0 300 300" + "\n"
                with open(self.path_command, mode='a') as f:
                    f.write(command)"""
            return ryuho + "^" + conjunction["buffer"] + conjunction["label"] + utterance["label"]

        if utterance_type == self.facilitation:
            utterance_length = 7
            self.length_of_latest_utterance += utterance_length
            command = str(sender) + ";" + "/say " + utterance["utterance"] + "[EOF]" + \
                      " /gesture " + random.choice(self.gestures_on_short_utterance)
            command += ";" + str(utterance_length) + "\n"
            with open(self.path_command, mode='a') as f:
                f.write(command)
            with open(self.path_log, mode='a') as f:
                f.write(str(time.perf_counter()) + "|" + command)
            return utterance["utterance"]

        if utterance_type == self.backchanneling:
            if utterance["attitude"] == '0' or utterance["attitude"] == '2' or utterance["attitude"] == '3':  # 賛成かニュートラルの相槌
                command = str(sender) + ";" + "/say " + conjunction["label"] + utterance["utterance"] + "[EOF]" +\
                    " /gesture " + random.choice(self.gestures_on_agreement)
            elif utterance["attitude"] == '1':  # 反対の相槌
                command = str(sender) + ";" + "/say " + conjunction["label"] + utterance["utterance"] + "[EOF]" +\
                    " /gesture " + random.choice(self.gestures_on_opposition)
            """utterance_length = self.wait_duration_calculation(conjunction["buffer"]) + \
                               self.wait_duration_calculation(utterance["utterance"])"""
            utterance_length = 1
            # self.length_of_latest_utterance += utterance_length
            command += ";" + str(utterance_length) + "\n"
            with open(self.path_command, mode='a') as f:
                f.write(command)
            with open(self.path_log, mode='a') as f:
                f.write(str(time.perf_counter()) + "|" + command)
            gaze = self.gaze_on_listening[sender]
            for j in range(len(gaze)):
                command = str(j) + ";" + gaze[j] + "\n"
                with open(self.path_command, mode='a') as f:
                    f.write(command)
                with open(self.path_log, mode='a') as f:
                    f.write(str(time.perf_counter()) + "|" + command)
            return conjunction["label"] + utterance["utterance"]


    def is_long_utterance(self, text):
        if len(text) > 20:
            return True
        else:
            return False

    def q_transition(self, utterance):
        # control=transitionによる状態の遷移
        try:
            if utterance["control"] == self.transition:
                prev = self.q
                self.q = int(utterance["argument"])
                self.q_sequence.append(self.q)
                self.turns_same_q = 0
                self.PACE = self.DEFAULT_PACE
                print("question " + str(prev) + " to " + str(self.q))
                return 1
        except KeyError:
            print("keyerror")
            return 0
        return 0

    def next_speaker_designation(self):
        while True:
            a = random.choice(range(self.PARTICIPANTS))
            if a != self.next_speaker:
                break
        return a

    def register_restrictions_and_utterance_itself(self, utterance_type, utterance, utterer):
        try:
            # utterance_typeはconjunctionかopinionかbackchanneling、utteranceは辞書の要素の型
            self.log_by_p[utterer][0].append(utterance["id"])
            if utterance_type == self.opinion:
                temp_restriction = utterance["restriction"].split(";")
                for i in temp_restriction:
                    if i != "":
                        self.log_by_p[utterer][1].append(i)
        # その発話をしたことによって禁止される発話を登録
            print([utterer, self.log_by_p[utterer][1]])
        except IndexError:
            print("utterer " + str(utterer) + "something went wrong")

    def fix_choices(self, who_to_send):
        print("fixing choice for P: " + str(who_to_send))
        choices = []
        control_labels = []
        for i in range(3):
            choice = self.fetch_choice(i)
            choices.append(choice)
            control_labels.append(choice["control"])
        print("reserved utterance", self.marked_utterance)

        conj1 = random.choice(self.conjunction_database[1])
        conj2 = random.choice(self.conjunction_database[3])
        if self.transition in control_labels:
            conj3 = random.choice(self.conjunction_database[4])
        else:
            conj3 = random.choice(self.conjunction_database[5])
        conjunctions = [conj1, conj2, conj3]
        # random.shuffle(conjunctions)

        # print(choices)
        # print(conjunctions)

        joker = self.conjunction_database[6][0]
        if self.q == 0:
            conjunctions = [joker, joker, joker]

        rtn = "/choice:" + str(who_to_send) + ":"
        for conjunction in conjunctions:
            rtn += conjunction["id"] + "," + conjunction["label"] + ";"
        rtn = rtn[:-1]
        rtn += ":"
        for choice in choices:
            rtn += choice["id"] + "," + choice["label"] + ";"
        rtn = rtn[:-1]
        return rtn

    def fetch_choice(self, who_to_send):  # QPDCではwho to sendが個人内でのナンバリングになる
        try:
            # 次の発話、接続詞を選ぶ
            # 選ばれている意見をマークする
            if self.turns_same_q <= min(self.PACE, len(self.utterance_database[self.q]) / 3):  # 遷移なしを優先して選ぶモード
                temp_v = []
                # 遷移なしの意見にとれるものがあれば取る
                for x in self.utterance_database[self.q]:
                    if x["control"] == "":
                        temp_v.append(x)
                random.shuffle(temp_v)
                for y in temp_v:
                    if y["id"] not in self.marked_utterance:
                        if y["id"] not in self.log_by_p[who_to_send][1] or True:
                            self.marked_utterance[who_to_send] = y["id"]
                            print(y["id"] + "/t<m, no transition")
                            return y

                # 遷移ありのものも含めて選ばせる
                for y in self.utterance_database[self.q]:
                    if y["id"] not in self.marked_utterance:
                        if y["id"] not in self.log_by_p[who_to_send][1] or True:
                            self.marked_utterance[who_to_send] = y["id"]
                            print(y["id"] + "/t<m, including transition")
                            return y
            else:
                temp_v = []
                # 遷移ありの発話が選ばれやすいようにする
                for i in range(min(2, len(self.utterance_database[self.q]))):
                    temp_v.append(random.choice(self.utterance_database[self.q]))
                for x in self.utterance_database[self.q]:
                    if x["control"] == self.transition:
                        temp_v.append(x)
                random.shuffle(temp_v)
                for y in temp_v:
                    if y["id"] not in self.marked_utterance:
                        if y["id"] not in self.log_by_p[who_to_send][1]:
                            self.marked_utterance[who_to_send] = y["id"]
                            print(y["id"] + "/t>=m, transition prioritized")
                            return y

            #　以上が話題をそのままにするか、深めるかで穏便に済むケース

            # qを遷移させる発話を持っている参加者がいる場合、現在のq内で候補を挙げられない場合は話を調整する発話をする
            """is_somebody_has_question = False
            for i in range(self.PARTICIPANTS):  # だれかqを遷移させる発話を持っているか
                if i == who_to_send:
                    continue
                else:
                    _, temp_check = self.id_search(self.marked_utterance[i])
                    print("is_somebody_has_question?", temp_check)
                    if temp_check["control"] == self.transition:
                        is_somebody_has_question = True
            if is_somebody_has_question:
                y = random.choice(self.facilitation_database)
                if y["id"] not in self.marked_utterance:
                    if y["id"] not in self.log_by_p[who_to_send][1]:
                        self.marked_utterance[who_to_send] = y["id"]
                        print(y["id"] + "/t>=m, unleashing somebody")
                        return y"""

            j = 0
            parent_qs = []
            temp_q_for_explore = self.q
            while True:
                j += 1
                print("back" + str(j) + "times")
                exp_t = self.dialogue_structure[temp_q_for_explore]["parent"]
                if exp_t == "" or j > 10 or exp_t == "0":
                    break
                try:
                    exp_t = int(exp_t)
                except ValueError:
                    break

                parent_qs.append(exp_t)
                temp_q_for_explore = exp_t
                # 今の問いへとつながる親たちを並べて取得
            print("back to previous leaf", parent_qs)

            i = 0
            for ex_q in parent_qs:
                i += 1
                temp_v = []
                for y in self.utterance_database[ex_q]:
                    if y["control"] == self.transition:
                        temp_v.append(y)
                for y in temp_v:
                    if y["id"] not in self.marked_utterance:
                        if y["id"] not in self.log_by_p[who_to_send][1] or True:
                            self.marked_utterance[who_to_send] = y["id"]
                            print(y["id"] + "/" + str(i) + " times back")
                            return y

            if len(self.q_sequence) == len(self.dialogue_structure) - 1:
                print("move to ending")
                return random.choice(self.ending_utterance)

        except KeyError:
            pass
        # 何も見つからなかったとき（エラー）
        return random.choice(self.facilitation_database)

    def send_choice(self, what_to_send, who_to_send):
        j = 0
        for c in self.clients:
            if j == who_to_send:
                c[0].sendto(what_to_send.encode('utf-8'), c[1])
            j += 1

    def send_logging(self, what_to_send):
        for c in self.clients:
            c[0].sendto(what_to_send.encode('utf-8'), c[1])

    def fix_choices_bc(self, who_to_send):
        bc_choices = []
        for i in range(4):
            sub = random.choice(self.backchanneling_database)
            while sub["attitude"] != str(i):
                sub = random.choice(self.backchanneling_database)
            bc_choices.append(sub)

        rtn = "/bc_ch:" + str(who_to_send) + ":"
        for bc in bc_choices:
            rtn += bc["id"] + "," + bc["label"] + ";"
        rtn = rtn[:-1]

        return rtn

    def process_message(self, sender, message):
        split_mes = message.split(":")
        if split_mes[0] == self.koushin:
            with open(self.path_log, mode='a') as f:
                f.write(str(time.perf_counter()) + "|" + str(sender) + ";" + self.koushin + "\n")
        elif split_mes[0] == self.hatsuwa:
            ids_in_mes = split_mes[1].split(";")
            if len(ids_in_mes[0]) > 0:
                _, conj = self.id_search(ids_in_mes[0])
            else:  # 接続語が入っていなかった場合はkyomuが入る
                _, conj = self.id_search("C6000")
            utterance_id = ids_in_mes[1]
            utterance_type, utterance = self.id_search(utterance_id)
            # 履歴の登録
            self.register_restrictions_and_utterance_itself(utterance_type, utterance, sender)
            self.delete_opinion_from_v(utterance_id)



            # コミューに送る命令を書く
            print("command to CommU is ", [conj, utterance])
            hatsuwa_content = self.write_command(sender, conj, utterance_type, utterance)
            # TLに出す用のログを吐く
            log = "/logging:" + str(sender) + ";" + utterance_type + ";" + hatsuwa_content
            print(log)
            self.send_logging(log)

            # 問いの遷移があれば、する
            tran = self.q_transition(utterance)
            """if tran:  # 問いの遷移があった時は発話は入れ替わる
                for i in range(self.PARTICIPANTS):
                    send_text = self.fix_choices(i)
                    self.send_choice(send_text, i)"""

            if utterance_type == self.opinion:
                self.turns_same_q += 1
                print("turns lasts for " + str(self.turns_same_q) + "cycles")


    def worker_thread(self, none):
        """クライアントとの接続を処理するハンドラ"""
        self.next_speaker = 0
        while True:
            # クライアントからの接続を待ち受ける (接続されるまでブロックする)
            # ワーカスレッド同士でクライアントからの接続を奪い合う
            clientsocket, (client_address, client_port) = self.serversocket.accept()
            self.clients.append((clientsocket, (client_address, client_port)))
            clientsocket.sendto(("you are number :" + str(len(self.clients) - 1)).encode('utf-8'), (client_address, client_port))
            print('New client: {0}:{1}'.format(client_address, client_port))
            # {重要}現時点では一旦接続が切れた場合のつなぎ直しは実装していません
            # クライアントは0からカウント　ユーザ0、ユーザ1、ユーザ2
            while True:
                try:
                    message = clientsocket.recv(1024)
                    raw_mes = message.decode('utf-8')

                    if raw_mes != "":
                        print("recv:" + raw_mes)
                        print(self.log_by_p)
                        if "hatsuwa" in raw_mes:
                            self.latest_operation_time.append(time.perf_counter())

                    # メッセージの内容とそれが誰から来たのかを取得
                    message = raw_mes
                    sender = self.sender_detection(client_address, client_port)
                    # print(self.latest_operation_time)
                    if True or self.latest_operation_time[-1] -  self.latest_operation_time[-2] > 2 or time.perf_counter() - self.latest_operation_time[-1] > 2:
                        self.process_message(sender, message)
                        if "hatsuwa" in raw_mes and "B" not in raw_mes:
                            if "00000" not in raw_mes:
                                self.next_speaker = self.next_speaker_designation()
                                self.speaker_log.append(self.next_speaker)
                                print(self.speaker_log)

                            print("elected next speaker is "+ str(self.next_speaker))
                            for i in range(len(self.clients)):
                                send_text = self.fix_choices_bc(i)
                                self.send_choice(send_text, i)
                                if i == self.next_speaker:
                                    send_text = self.fix_choices(i)
                                    self.send_choice(send_text, i)
                                else:
                                    self.send_choice("/taiki:", i)
                        if "jidou" in raw_mes:  # 新しいbcが来ていない場合は端末側のbc表示はしないようにする
                            jidou_hatsuwa = random.choice(self.pass_to_others_database)
                            self.process_message(sender, "hatsuwa:;" + jidou_hatsuwa["id"])
                            self.PACE -= 1
                            self.next_speaker = self.next_speaker_designation()
                            print("elected next speaker is "+ str(self.next_speaker))
                            for i in range(len(self.clients)):
                                if i == self.next_speaker:
                                    send_text = self.fix_choices(i)
                                    self.send_choice(send_text, i)
                                else:
                                    self.send_choice("/taiki:", i)
                        if "rireki" in raw_mes:
                            for i in range(self.PARTICIPANTS):
                                self.send_choice(raw_mes + "#", i)

                    else:
                        print("----passed due to consecutive operation")

                except OSError:
                    break

            clientsocket.close()
            print('Bye-Bye: {0}:{1}'.format(client_address, client_port))
            # {重要}現在クライアントとの接続が一度切れると、それ以降どこかのクライアントからメッセージが送信されるたびにそのクライアントとの接続が切れるようになる


if __name__ == '__main__':
    def_port = 50000
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('192.168.100.1', 80))
    ip = s.getsockname()[0]
    print("waiting at :" + ip + ":" + str(def_port))
    s = DialogManager(ip, def_port, TOPIC_ID=0)
    # s = DialogManager('127.0.0.1', 50000, TOPIC_ID=0)