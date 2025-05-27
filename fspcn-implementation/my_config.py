import os


class MyConfig:
    def __init__(self):
        self.graphic_terminal = True
        self.verbose_log = False
        self.my_configuration = "firstattempt"
        self.result_folder = "result"
        self.data_folder = "data"

        try:
            os.stat(self.result_folder)
        except:
            os.mkdir(self.result_folder)
