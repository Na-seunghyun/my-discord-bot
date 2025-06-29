from flask import Flask, Response, request
import threading

app = Flask(__name__)

@app.route("/", methods=["GET", "HEAD"])
def health_check():
    if request.method == "HEAD":
        return Response(status=200)  # 본문 없이 200 OK 응답
    return "봇이 실행 중입니다!", 200

def run():
    app.run(host="0.0.0.0", port=8000)

def keep_alive():
    thread = threading.Thread(target=run)
    thread.daemon = True
    thread.start()
    print("✅ 헬스 체크 서버 실행 중 (8000)")
