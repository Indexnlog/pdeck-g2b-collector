import base64
import os

# 현재 폴더에 있는 service_account.json 파일을 찾습니다
file_path = "service_account.json"

if os.path.exists(file_path):
    with open(file_path, "rb") as f:
        encoded_string = base64.b64encode(f.read()).decode("utf-8")

    print("\n👇 아래 값을 복사해서 GitHub Secret에 넣으세요 👇\n")
    print(encoded_string)
    print("\n" + "="*30)
else:
    print(f"❌ '{file_path}' 파일을 찾을 수 없습니다. 파일이 같은 폴더에 있는지 확인해주세요!")
