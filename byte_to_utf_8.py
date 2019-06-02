# coding: utf-8
'''
参考用
mystery = b"\xe5\x88\xab"
x = mystery.decode('utf-8')
print(x)
y = bytearray.fromhex(\xe5\x88\xab).decode()
print(y)
'''

var = 1
while var == 1:
    a = input('输入UTF-8的16进制编码：\n')

    b = list(a)

    # print(b)

    leng = len(b)

    i = 0

    while (i < (1.5 * leng)):
        b.insert(i, '\\x')
        i += 3

    # print(b)

    c = str(''.join(b))

    # print(c)

    d = 'b' + "'" + c + "'"

    # print(d)

    x = eval(d).decode('utf8')
    print('转换结果为:\n\n\n{}\n\n'.format(x))
