import base64
import os

target = "service_account.json"

if os.path.exists(target):
    with open(target, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    print("\n👇 아래 값을 복사해서 GitHub Secret에 넣으세요 (따옴표 제외) 👇\n")
    print(encoded)
    print("\n" + "="*30)
else:
    print("❌ service_account.json 파일이 없습니다! 다운로드 폴더에서 가져오세요.")
