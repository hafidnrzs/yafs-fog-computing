
import os


class myConfig:
    def __init__(self):
        self.graphicTerminal = False
        self.verbose_log = False
        self.myConfiguration_ = "exp"
        self.resultFolder = "data"

        try:
            os.stat(self.resultFolder)
        except:
            os.mkdir(self.resultFolder)
