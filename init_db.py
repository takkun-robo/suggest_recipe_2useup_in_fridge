import sqlite3

# データベースに接続（なければ新規作成）
conn = sqlite3.connect('database.db')
c = conn.cursor()

# itemsテーブルを作成
# id: ユニークな識別番号
# name: 食材名 (テキスト)
# expiry_date: 賞味期限 (テキスト)
c.execute('''
    CREATE TABLE items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        expiry_date TEXT NOT NULL
    )
''')

# 変更を保存して閉じる
conn.commit()
conn.close()
