import time
import requests
res=requests.get(url='http://www.pandahome023.cn/analysis/api.php?id=161')
print(res.text)
print("状态码:", res.status_code)
# if res.text.find("禁止访问")>-1:
#    while True:
#        time.sleep(1)