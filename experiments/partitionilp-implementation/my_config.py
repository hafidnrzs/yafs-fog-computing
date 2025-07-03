import os


class MyConfig:
    def __init__(self):
        self.graphic_terminal = False
        self.verbose_log = True
        self.my_configuration = "fspcn"
        self.result_folder = "result"
        self.data_folder = "data"

        # try:
        #     os.stat(self.result_folder)
        # except:
        #     os.mkdir(self.result_folder)
