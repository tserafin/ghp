from ctypes import *

class barley_amount(Union):
    _fields_ = [
        ("barley_long", c_long),
        ("barley_int", c_int),
        ("barley_char", c_char * 8),
    ]

value = raw_input("Enter amount:")
num = barley_amount(int(value))
print num.barley_long
print num.barley_int
print num.barley_char