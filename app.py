import os
from datetime import date
from dotenv import load_dotenv
# import sqlite3
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
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


# --- ここからデータベース設定 ---
# 1. 環境変数からDATABASE_URLを取得（Renderの本番環境用）
# 2. なければ、ローカル用のSQLiteデータベースを指すようにする
db_uri = os.environ.get('DATABASE_URL', 'sqlite:///database.db')
# PostgreSQLのURLが古い形式の場合、SQLAlchemyが対応する形式に変換
if db_uri.startswith("postgres://"):
    db_uri = db_uri.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_uri
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # 不要な警告を抑制
db = SQLAlchemy(app)
# --- データベース設定ここまで ---

# --- データベースモデル定義 ---
# itemsテーブルの構造をPythonのクラスとして定義
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    expiry_date = db.Column(db.Date, nullable=False)
    storage_location = db.Column(db.String(50), nullable=True, default='冷蔵庫')

    def __repr__(self):
        return f'<Item {self.name}>'
# --- モデル定義ここまで ---


# (get_db_connection, get_item, index, add, delete, edit関数は変更なし)
# def get_db_connection():
#     conn = sqlite3.connect('database.db')
#     conn.row_factory = sqlite3.Row
#     return conn

# def get_item(item_id):
#     conn = get_db_connection()
#     item = conn.execute('SELECT * FROM items WHERE id = ?', (item_id,)).fetchone()
#     conn.close()
#     return item

@app.route('/')
def index():
    # conn = get_db_connection()
    # items_from_db = conn.execute('SELECT * FROM items ORDER BY expiry_date ASC').fetchall()
    # conn.close()
    items_from_db = Item.query.order_by(Item.expiry_date.asc()).all()
    
    items_with_status = []
    today = date.today()
    for item in items_from_db:
        time_left = item.expiry_date - today
        status = 'safe'
        if time_left.days < 0:
            status = 'danger'
        elif time_left.days <= 3:
            status = 'warning'
        
        items_with_status.append({
            'id': item.id,
            'name': item.name,
            'expiry_date': item.expiry_date.isoformat(), # HTMLで扱いやすいように文字列に変換
            'storage_location': item.storage_location or '冷蔵庫',
            'status': status
        })

    return render_template('index.html', items=items_with_status)

@app.route('/add', methods=('POST',))
def add():
    name = request.form['name']
    expiry_date_str = request.form['expiry_date']
    storage_location = request.form.get('storage_location', '冷蔵庫')
    
    # 新しいItemオブジェクトを作成してデータベースに追加
    new_item = Item(name=name, expiry_date=date.fromisoformat(expiry_date_str), storage_location=storage_location)
    db.session.add(new_item)
    db.session.commit() # 変更を確定
    
    return redirect(url_for('index'))

@app.route('/<int:id>/delete', methods=('POST',))
def delete(id):
    # conn = get_db_connection()
    # conn.execute('DELETE FROM items WHERE id = ?', (id,))
    # conn.commit()
    # conn.close()
    item_to_delete = Item.query.get_or_404(id)
    db.session.delete(item_to_delete)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/<int:id>/edit', methods=('GET', 'POST'))
def edit(id):
    # item = get_item(id)
    item_to_edit = Item.query.get_or_404(id)
    if request.method == 'POST':
        # name = request.form['name']
        # expiry_date = request.form['expiry_date']
        # conn = get_db_connection()
        # conn.execute('UPDATE items SET name = ?, expiry_date = ? WHERE id = ?',
        #              (name, expiry_date, id))
        # conn.commit()
        # conn.close()
        item_to_edit.name = request.form['name']
        item_to_edit.expiry_date = date.fromisoformat(request.form['expiry_date'])
        item_to_edit.storage_location = request.form.get('storage_location', '冷蔵庫')
        db.session.commit()
        return redirect(url_for('index'))
    
    # GETリクエストの場合は、日付を正しいフォーマットでedit.htmlに渡す
    item_for_template = {
        'id': item_to_edit.id,
        'name': item_to_edit.name,
        'expiry_date': item_to_edit.expiry_date.isoformat(),
        'storage_location': item_to_edit.storage_location or '冷蔵庫'
    }

    return render_template('edit.html', item=item_for_template)


@app.route('/menu', methods=('GET', 'POST'))
def menu():
    suggestion = None
    if request.method == 'POST':
        # 賞味期限が近い順に食材を取得（期限切れは除く）
        items = Item.query.filter(Item.expiry_date >= date.today()).order_by(Item.expiry_date.asc()).all()
        
        food_list = ", ".join([f"{item.name}（賞味期限: {item.expiry_date.isoformat()}）" for item in items])
          
        if food_list:
            today_str = date.today().isoformat()
            prompt = f"""
            # 命令
            あなたはプロの料理研究家です。以下の制約条件と食材リストを元に、家庭で簡単に作れる献立を3つ提案してください。

            # 制約条件
            ・賞味期限が今日（{today_str}）に近い食材を優先的に使うように献立を考えてください。
            ・料理名と、具体的な手順を2～3行で分かりやすく説明してください。
            ・出力形式は以下のMarkdown形式を必ず守ってください。

            **【提案1：料理名】**
            - 手順1
            - 手順2

            **【提案2：料理名】**
            - 手順1
            - 手順2

            """
            contents=f'''
以下は食材リストです（賞味期限が近い順）．
{food_list}
'''
            
            try:

                response = LLM_client.models.generate_content(
                    model=LLM_model,
                    config=types.GenerateContentConfig(
                        system_instruction=prompt
                    ),
                    contents=contents
                )
                suggestion = response.text
            except Exception as e:
                # APIからのエラーをより具体的に表示
                suggestion = f"APIとの通信中にエラーが発生しました: {e}"
        else:
            suggestion = "賞味期限内の食材が登録されていません。まずは食材を登録してください。"
            
    return render_template('menu.html', suggestion=suggestion)

# アプリケーションコンテキスト内でデータベーステーブルを作成
with app.app_context():
    db.create_all()


if __name__ == '__main__':
    app.run(debug=True)
