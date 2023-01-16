# MicroPython ST7567 LCD driver, SPI interfaces

from micropython import const
import framebuf
import time

# register definitions
DISPON = const(0xAF)
DISPOFF = const(0xAE)
SET_START_LINE = const(0X40)  #后6位为起始行
SET_PAGE_ADDR =  const(0xB0)  #后4位是页地址

SET_SEG_DIR   =  const(0xA0)  #最后一位是方向
SET_DISP_INV  =  const(0x21)  #最后一位是反转
ALL_PIXEL_ON  =  const(0xA4)  #最后一位是设置
BIAS_SELECT   =  const(0xA2)  #最后一位是设置
SOFT_RESET    =  const(0xE2)
SET_COM_DIR   =  const(0xC0)  #第四位是设置
POWER_CONT    =  const(0x28)  #后3位是三个设置
REG_RATIO     =  const(0x20)  #后3位是设置
NOP           =  const(0xE3)
RELEASE_N_LINE=  const(0x84)
SPI_READ_STAT =  const(0xFC)
SPI_READ_DDRAM=  const(0xF4)
EXT_COMM_SET  =  const(0xFE)  #后1位是设置
#注意以下是两字节命令
SET_EV        =  const(0x81)  #后跟随的字节的6位是数据
SET_BOOTER    =  const(0xF8)  #后跟随的字节的1位是数据  
SET_COL_ADDR  =  const(0x10)  #后四位是列高位#后跟随的字节4位是列低位
  
SET_N_LINE    =  const(0x85)  #后跟随的字节的5位是数据 

SET_DISP_MODE =  const(0x70)  #第二位是设置允许，决定下面三个命令的有效
SET_DISP_DUTY =  const(0xD0)  #后3位是占空比
SET_DISP_BIAS =  const(0x90)  #后3位是偏置
SET_DISP_FRATE=  const(0x98)  #后3位是帧率


# Subclassing FrameBuffer provides support for graphics primitives
# http://docs.micropython.org/en/latest/pyboard/library/framebuf.html
class UC1609(framebuf.FrameBuffer):
    
    def __init__(self, width, height):
        
        self.width = width
        self.height = height
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)
        if self.rot==0 or self.rot==2:
            super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB, self.width)
        else:
            super().__init__(self.buffer, self.height, self.width, framebuf.MONO_HMSB, self.height)
        self.init_display()

    def init_display(self):
        if self.res==None:
            self.write_cmd(0xe2)
        else:
            self.res(1)
            time.sleep_ms(10)
            self.res(0)
            time.sleep_ms(100)
            self.res(1)
        time.sleep_ms(10)
        cmd_list=[
            0xae,  #禁用显示，避免未清理的ram数据显示
            0x24,  #设置温度补偿24-27
            0x2f,  #设置电源控制28-2f
            0xeb,  #设置Bias Ratio e8-eb
            0x81,0xb4,  #设置 PM[7:0]
            0x40,  #Set Scroll Line  40-7f
            0x33,0x2a,  #Set APC[R][7:0],
            0xc4,  #Set LC[2:1]
            0xf1,0x3f,  #Set COM End
            ]
        if self.rot==0:
            cmd_list.extend([
            0xC4,   #显示方向调整，行镜像
            0x89,   #数据写自增，行优先
            ])
        elif self.rot==1:
            cmd_list.extend([
            0xC0,   #显示方向调整，原始
            0x8B,   #数据写自增，列优先
            ])            
        elif self.rot==2:
            cmd_list.extend([
            0xC2,   #显示方向调整，列镜像
            0x89,   #数据写自增，行优先
            ])            
        elif self.rot==3:
            cmd_list.extend([
            0xC6,   #显示方向调整，行列镜像
            0x8B,   #数据写自增，列优先
            ])
       
        for cmd in cmd_list:  
            self.write_cmd(cmd)
        self.fill(0)
        self.show()
        self.poweron()
        
    def poweroff(self):
        self.write_cmd(0xae)

    def poweron(self):
        self.write_cmd(0xaf)

    def contrast(self, contrast):
        self.write_cmd(REG_RATIO|(contrast&0x07))

    def invert(self, invert):
        self.write_cmd(SET_DISP_INV | (invert >0))

    def show(self):
        self.write_cmd(0xb0)
        self.write_cmd(0x10)
        self.write_cmd(0x00)
        self.write_data(self.buffer)
        return
        for page in range(8):
            self.write_cmd(SET_PAGE_ADDR|page)
            self.write_cmd(SET_COL_ADDR|((start&0xf0)>>4))
            self.write_cmd(start&0x0f)
            self.write_data(self.buffer[page*192:(page+1)*192])

class UC1609_I2C(UC1609):
    def __init__(self, width, height, i2c, addr=0x3C, res=None, rot=1):
        self.i2c = i2c
        self.addr = addr
        self.res = res
        self.rot=rot
        if res!=None:
            res.init(res.OUT, value=0)
        super().__init__(width, height)
    def write_cmd(self, cmd):
        self.i2c.writeto(self.addr, bytearray([cmd]))
    def write_data(self, buf):
        self.i2c.writeto(self.addr+1, buf)

class UC1609_SPI(UC1609):
    def __init__(self, width, height, spi, dc=None, res=None, cs=None, rot=1):
        if res!=None:
            res.init(res.OUT, value=0)
            self.res = res
        if dc==None or cs==None:
            print("Must provide a cs and dc")
            return
        dc.init(dc.OUT, value=0)
        cs.init(cs.OUT, value=1)
        self.spi = spi
        self.dc = dc
        self.cs = cs
        self.rot=rot
        super().__init__(width, height, res=None, rot=rot)

    def write_cmd(self, cmd):
        self.dc(0)
        self.cs(0)
        self.spi.write(bytearray([cmd]))
        self.cs(1)

    def write_data(self, buf):
        self.dc(1)
        self.cs(0)
        self.spi.write(buf)
        self.cs(1)