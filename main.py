import requests
from lxml import etree
import re
import pymysql


host = 'https://www.infineon.com'
conn = pymysql.connect(host='localhost', port=3306, user="your_user", passwd='your_pwd', charset='utf8mb4', database="isee")
cur = conn.cursor()

ctable = 'create table plist(id int primary key auto_increment , category varchar(100), cid int)'
dctable = 'drop table plist'

ptable = 'create table product(id int primary key auto_increment, name varchar(100), min float, max float, instruct varchar(400), package varchar(50), pdf varchar(200), cid int not null)'
dptable = 'drop table product'

cur.execute(dctable)
cur.execute(dptable)
conn.commit()
cur.execute(ctable)
cur.execute(ptable)
conn.commit()


# 三次失败重试
def get_response(url):
    count = 0
    while count < 3:
        try:
            if count == 0:
                req = requests.get(url=url, timeout=60)
            else:
                req = requests.get(url=url, timeout=30)
            return req
        except Exception as e:
            count += 1


# 获取除了ASIC, BatteryManagement, 高可靠性器件之外的顶级分类信息
def get_top_ctg() -> list:
    req = get_response('https://www.infineon.com/cms/cn/services/ajax/navigationsection.html?path=%2Fen%2Fproduct%2F.content%2Fnavigationsection%2Fn_00002.html')
    tree = etree.HTML(req.text)
    div_lst = tree.xpath("//div[@class='col-xxs-6 col-md-7']/div")
    lst = []
    for i in div_lst:
        res = str(i.xpath("./ul/li[1]/a/text()")[0])
        href = i.xpath("./ul/li[1]/a/@href")
        if res.startswith('ASIC') or res.startswith('Battery') or res.startswith('高可靠性器件') or res.startswith('Wireless') or res.startswith('Universal') or res.startswith('Clocks'):
            continue
        lst.append([res, host + href[0]])
    return lst


# 获取料号
def get_title(tree):
    title = tree.xpath("//h1[@class='page-title']/span/text()")
    if title:
        return title[0]
    return 'NULL'


# 获取产品表中产品的URL, text为产品表的JSON文本
def get_product_table(text):
    res = re.findall('"openCmsPath":"(.*?)"', text, re.S)
    for i in range(0, len(res)):
        res[i] = host + res[i]
    return res


# 提取产品表URL, text为当前页面的html源代码
def get_product_table_url(text: str) -> str:
    res = re.findall(
        '&#x7b;&quot;tableConfigId&quot;&#x3a;&quot;(.*?)&quot;,&quot;collectionId&quot;&#x3a;&quot;(.*?)&quot;,&quot;collectionType&quot;&#x3a;&quot;(.*?)&quot;,&quot;showAllOPNs&quot;&#x3a;(.*?)&#x7d;',
        text, re.S)
    url = 'https://www.infineon.com/products/pc/frontendprecalculation?tableconfigid=' + res[0][0] + '&collectionid=' + res[0][1] + '&collectiontype=' + res[0][2] + '&showallopns=' + 'true' + '&calculatefilters=true'
    return url


# 去除空格之外的空白
def no_space(text: str) -> str:
    return text.strip()


# 判断是否为产品列表的第一种方法
def are_you_plist1(tree) -> bool:
    rst = tree.xpath("//section[@class='subcategories']")
    if rst:
        return True
    else:
        return False


# 判断是否为产品列表的第二种方法
def are_you_plist2(text: str) -> bool:
    res = re.findall(
        '&#x7b;&quot;tableConfigId&quot;&#x3a;&quot;(.*?)&quot;,&quot;collectionId&quot;&#x3a;&quot;(.*?)&quot;,&quot;collectionType&quot;&#x3a;&quot;(.*?)&quot;,&quot;showAllOPNs&quot;&#x3a;(.*?)&#x7d;',
        text, re.S)
    if res:
        return True
    else:
        return False


# 判断是否为产品列表
def is_plist(text) -> bool:
    tree = etree.HTML(text=text)
    if are_you_plist1(tree) or are_you_plist2(text=text):
        return True
    else:
        return False


# 获取子菜单的子菜单，过滤掉综述，防止爬取到重复数据
def get_url1(tree) -> list:
    sub_urls = tree.xpath('//ul[contains(@class,"subcategoryNavColumn__sublist")]/li/a/@href')
    sub_text = tree.xpath('//ul[contains(@class,"subcategoryNavColumn__sublist")]/li/a/text()')
    new_list = []
    for i in range(0, len(sub_text)):
        if sub_text[i] != '综述' and sub_text[i] != 'Overview':
            new_list.append(host + sub_urls[i])
    return new_list


# 抓取子菜单的条目，过滤掉url为javascript的子菜单
def get_url2(tree) -> list:
    rst = tree.xpath("//li[@class='subcategoryNavColumn__item']/a/@href")
    new_list = []
    for i in rst:
        if i != 'javascript:':
            new_list.append(host + i)
    return new_list


# 获取简介
def get_instruct(tree):
    rst = tree.xpath("//section[@class='content']/p[@class='h2']/text()")
    if rst:
        return rst[0]
    return 'NULL'


# 获取ispnID号， 用于获取指标参数
def get_ispnid(text):
    rst = re.findall("ispnId: '(.*?)'", text, re.S)
    if rst:
        return rst[0]
    return ''


# 获取pdf链接
def get_pdf_link(tree) -> str:
    link_lst = tree.xpath("//meta[@name='doc_url']/@content")
    if link_lst:
        return host + link_lst[0]
    return 'NULL'


# 获取指标参数URL
def get_param_url(text):
    url = get_ispnid(text)
    return 'https://www.infineon.com/products/pc/parametrics?lang=en&ispnId=' + url


# 匹配到就返回匹配到的值，匹配不到返回None
def get_package(text: str):
    ppos = text.rfind('"nameFormatted":"Package"')
    spos = text.rfind('stringValue', 0, ppos)
    rst = re.search('stringValue":"(.*?)"', text[spos: ppos], re.S)
    if rst:
        return rst.groups()[0]
    else:
        return None


# 获取温度指标。如果匹配成功，则返回值为3个数，第一个数是最高温度，第二个数是最低温度
def get_temperature(text: str):
    tpos = text.rfind("Operating Temperature")
    if tpos < 0:
        return ['NULL', 'NULL']
    vpos = text.rfind('minValueBaseUnit', 0, tpos)
    mpos = text.rfind('maxValueBaseUnit', 0, tpos)
    if vpos < 0 and mpos < 0:
        return ['NULL', 'NULL']
    info_str = text[vpos: tpos]
    min_rst = re.search('"maxValueDisplayUnit":.*?,"nameFormatted":".*?",.*?"minValueDisplayUnit":(.*?),', info_str, re.S)
    max_rst = re.search('"maxValueDisplayUnit":(.*?),"nameFormatted":".*?",.*?"minValueDisplayUnit":.*?,', info_str, re.S)
    if min_rst:
        if min_rst.groups()[0] == 'null':
            min_rst = 'NULL'
        else:
            min_rst = float(min_rst.groups()[0])
    else:
        min_rst = 'NULL'
    if max_rst:
        if max_rst.groups()[0] == 'null':
            max_rst = 'NULL'
        else:
            max_rst = float(max_rst.groups()[0])
    else:
        max_rst = 'NULL'
    return [max_rst, min_rst]


# 获取需要的参数
def get_target_data(text):
    tree = etree.HTML(text)
    name = get_title(tree)
    instruct = no_space(get_instruct(tree))
    url = get_param_url(text)
    req = get_response(url)
    package = get_package(req.text)
    lst = get_temperature(req.text)
    pdf = get_pdf_link(tree)
    maxtmp = lst[0]
    mintmp = lst[1]
    return {'min': mintmp, 'max': maxtmp, 'name': name, 'instruct': instruct, 'package': package, 'pdf': pdf}


# 第一种获取产品列表的方法
# return: 返回一个列表，其每个元素都是子产品的url
def get_plist1(tree) -> list:
    u1 = get_url1(tree)
    u2 = get_url2(tree)
    u1.extend(u2)
    return list(set(u1))


# 第二种获取产品列表的方法
def get_plist2(text):
    url = get_product_table_url(text)
    req = get_response(url=url)
    urls = get_product_table(req.text)
    return urls


# 获取产品列表。该方法先调用第一种获取产品列表的方法，再调用第二种获取产品列表的方法。之所以这么做是因为先调用第二种方法会引起分类混乱
def get_plist(text: str):
    tree = etree.HTML(text)
    res = get_plist1(tree)
    if res:
        return res
    res = get_plist2(text)
    if res:
        return res
    return None


# 保存数据到产品表
def save_plist(name: str, father_id: int) -> int:
    sql = 'select id from plist where category=%s&&cid=%s'
    cur.execute(sql, (name, father_id))
    res = cur.fetchone()
    if not res:
        sql = "insert into plist (category, cid)values(%s, %s)"
        cur.execute(sql, (name, father_id))
        conn.commit()
        sql = 'select id from plist where category=%s&&cid=%s'
        cur.execute(sql, (name, father_id))
        res = cur.fetchone()
        return res[0]

    else:
        return res[0]


# 将当前产品的标题存入数据库
def process_plist(text: str, father_id: int) -> list:
    rst = get_plist(text)
    tree = etree.HTML(text)
    name = get_title(tree)
    cid = save_plist(name=name, father_id=father_id)
    print("Save category: " + name)
    return [rst, cid]


# 把数据存入数据库
def save_into_product(dct: dict, father_id: int):
    sql = 'insert into product (name, min, max, instruct, package, pdf, cid)values(%s, %s, %s, %s, %s, %s, %s)'
    if dct['min'] == 'NULL':
        dct['min'] = None
    if dct['max'] == 'NULL':
        dct['max'] = None
    if dct['instruct'] == 'NULL':
        dct['instruct'] = None
    if dct['package'] == 'NULL':
        dct['package'] = None
    print(dct)
    try:
        cur.execute(sql, (dct['name'], dct['min'], dct['max'], dct['instruct'], dct['package'], dct['pdf'], father_id))
        conn.commit()
        print('Save Success.')
    except Exception as e:
        print(e)


# 下载pdf
def dl_pdf(url, name):
    name = 'infineon' + '--' + name + '.pdf'
    req = get_response(url)
    with open("./pdf_files/" + name, 'wb') as f:
        f.write(req.content)


def process_product(text: str, father_id: int):
    data = get_target_data(text)
    if data['pdf'] == 'NULL' or data['name'] == 'NULL':
        return 0
    dl_pdf(data['pdf'], data['name'])
    data['pdf'] = 'infineon' + '--' + data['name'] + '.pdf'
    save_into_product(data, father_id)


def wrong_log(e, url):
    with open("./wrong_log.log", 'a') as f:
        f.write(url)
        f.write('\n')
        f.write(str(e))
        f.write('\n')


def main(url, father_id):
    try:
        res = get_response(url=url)
        print("Request URL: ", url)
        if res.status_code == 404:
            print("Request URL Error: 404: " + url)
            return 0
        elif is_plist(res.text):
            data = process_plist(res.text, father_id)
            for pct in data[0]:
                main(pct, father_id=data[1])
        else:
            process_product(res.text, father_id)
    except Exception as e:
        print('*' * 20)
        print(e)
        print('*' * 20)
        wrong_log(e, url)


top_lst = get_top_ctg()
for lt in top_lst:
    tid = save_plist(lt[0], 0)
    main(lt[1], tid)

cur.close()
conn.close()
