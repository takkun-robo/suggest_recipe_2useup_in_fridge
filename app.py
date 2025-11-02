import os
from datetime import date
from dotenv import load_dotenv
import sqlite3
from flask import Flask, render_template, request, redirect, url_for
from google import genai
from google.genai import types


# .envファイルから環境変数を読み込む
load_dotenv()

app = Flask(__name__)

# LLMの設定．今はgemini
# gemini api key が設定されてるか確認
if not os.environ.get('GOOGLE_LLM_API_KEY'):
    print('GOOGLE_LLM_API_KEY is not found.')
    print('maybe that value is not set in dotenv?')
# gemini apiのクライアント作成
LLM_client = genai.Client(api_key=os.environ.get('GOOGLE_LLM_API_KEY'))
# geminiのせっていもろもろ
LLM_model = 'gemini-2.5-flash'


# (get_db_connection, get_item, index, add, delete, edit関数は変更なし)
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_item(item_id):
    conn = get_db_connection()
    item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()
    conn.close()
    return item

@app.route('/')
def index():
    conn = get_db_connection()
    items_from_db = conn.execute('SELECT * FROM items ORDER BY expiry_date ASC').fetchall()
    conn.close()
    items_with_status = []
    today = date.today()
    for item in items_from_db:
        item_dict = dict(item)
        expiry_date = date.fromisoformat(item['expiry_date'])
        time_left = expiry_date - today
        if time_left.days < 0:
            item_dict['status'] = 'danger'
        elif time_left.days <= 3:
            item_dict['status'] = 'warning'
        else:
            item_dict['status'] = 'safe'
        items_with_status.append(item_dict)
    return render_template('index.html', items=items_with_status)

@app.route('/add', methods=('POST',))
def add():
    name = request.form['name']
    expiry_date = request.form['expiry_date']
    conn = get_db_connection()
    conn.execute('INSERT INTO items (name, expiry_date) VALUES (?, ?)',
                 (name, expiry_date))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/<int:id>/delete', methods=('POST',))
def delete(id):
    conn = get_db_connection()
    conn.execute('DELETE FROM items WHERE id = ?', (id,))
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

@app.route('/<int:id>/edit', methods=('GET', 'POST'))
def edit(id):
    item = get_item(id)
    if request.method == 'POST':
        name = request.form['name']
        expiry_date = request.form['expiry_date']
        conn = get_db_connection()
        conn.execute('UPDATE items SET name = ?, expiry_date = ? WHERE id = ?',
                     (name, expiry_date, id))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))
    return render_template('edit.html', item=item)


# ↓↓↓ ここから menu 関数を新しいAPIの作法に修正 ↓↓↓
@app.route('/menu', methods=('GET', 'POST'))
def menu():
    suggestion = None
    if request.method == 'POST':
        conn = get_db_connection()
        items = conn.execute('SELECT name FROM items WHERE expiry_date >= ?', (date.today(),)).fetchall()
        conn.close()
        
        food_list = ", ".join([item['name'] for item in items])
        
        if food_list:
            prompt = f"""
            # 命令
            あなたはプロの料理研究家です。以下の制約条件と食材リストを元に、家庭で簡単に作れる献立を3つ提案してください。

            # 制約条件
            ・料理名と、具体的な手順を2～3行で分かりやすく説明してください。
            ・出力形式は以下のMarkdown形式を必ず守ってください。

            **【提案1：料理名】**
            - 手順1
            - 手順2

            **【提案2：料理名】**
            - 手順1
            - 手順2

            """
            contents='''
以下は食材リストです．
{food_list}
'''
            
            try:

                suggestion = LLM_client.models.generate_content(
                    model=LLM_model,
                    config=types.GenerateContentConfig(
                        system_instruction=prompt
                    ),
                    contents=contents
                )
            except Exception as e:
                # APIからのエラーをより具体的に表示
                suggestion = f"APIとの通信中にエラーが発生しました: {e}"
        else:
            suggestion = "冷蔵庫に賞味期限内の食材がありません。まずは食材を登録してください。"
            
    return render_template('menu.html', suggestion=suggestion)
# ↑↑↑ menu 関数の修正はここまで ↑↑↑

if __name__ == '__main__':
    app.run(debug=True)
