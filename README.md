This project is using for download all pdf file from infineon.com(it will only download the file which needn't login).

This project is single process, single thread, and it's not async.So it will be very slowly(and this site's speed is very slow, too).

To be honestly, this spider is very terrible.Because it's not scalable.This is the first time I write this kind of spider, and I only have two days, so I can't design it good.But you can have a good look at those function to get informations what you need, those functions are very clearly, they can help you to know the rules of this site.

This spider will get the title, instruction, package temperature info and download pdf file.
To use this project, you should import those requirement package: requests, lxml, pymysql.You can use pip to get them.

If you installed those packages, you should change some code with main.py.You should change the connect about pymysql.You should enter your own database, your databse charset, your own username your own password.

After you changed those code, you should create a directory at ./pdf\_files.Because the pdf file will be saved at this directory.

When the spider meet something which can't be solved, it will write a log at ./wrong\_log.log.
Then you can start spider.

