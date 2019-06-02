#!/usr/bin/python
# -*- coding: UTF-8 -*-
import numpy as np
# 打开文件
a = [[1,2,3],[4,5,6],[7,8,9]]

a = np.array(a)
a_ = a.T


b = np.dot(a,a_)
print(b)