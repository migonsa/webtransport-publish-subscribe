import sqlite3, math
from contextlib import closing


def clear_db(conn):
    with closing(conn.cursor()) as c:
        c.execute("DELETE FROM perms")
        c.execute("DELETE FROM topics")
        c.execute("DELETE FROM clients")
    conn.commit()

def create_topics_and_perms(db, nt, hp, cp, hs, cs, password):
    conn = sqlite3.connect(db)
    clear_db(conn)
    clients = []
    for i in range(hp):
        for j in range(cp):
            clients.append("hp%d_%d" % (i+1, j+1))
    for i in range(hs):
        for j in range(cs):
            clients.append("hs%d_%d" % (i+1, j+1))
    digits = int(math.log10(nt))+1
    inserts1 = []
    inserts2 = []
    with closing(conn.cursor()) as c:
        for i in range(1, nt+1):
            format = 'topic%' + '0' + str(digits) + 'd'
            format = format % (i)
            inserts1.append((i,format))
        c.executemany("INSERT INTO topics VALUES(?,?)", inserts1)
        inserts1 = []
        for i in range(len(clients)):
            user = clients[i]
            inserts1.append((i+1,clients[i],password))
            for j in range(1, nt+1):
                inserts2.append((i+1,j))
        c.executemany("INSERT INTO clients VALUES(?,?,?)", inserts1)
        c.executemany("INSERT INTO perms VALUES(?,?,1,1)",inserts2)
    conn.commit()
    conn.close()