# BMS 타임영역 뒤 두 자리 NN을 01로 치환하고, 마디 단위로 개행 추가

input_bms = "output.bms"
output_bms = "output_modified.bms"

with open(input_bms, "r", encoding="utf-8") as f:
    lines = f.readlines()

new_lines = []
prev_ttt = None  # 이전 마디 번호 저장

for line in lines:
    if line.startswith("#") and ":" in line:
        header, data = line.split(":", 1)
        # header 예: #00301 -> #003 + 01
        if len(header) >= 6:
            ttt = header[1:4]  # 마디 번호
            new_header = f"#{ttt}01"  # NN을 01로 고정
            new_line = f"{new_header}:{data}"

            # 이전 마디와 다른 경우, 마디 구분 개행 추가
            if prev_ttt is not None and ttt != prev_ttt:
                new_lines.append("\n")
            prev_ttt = ttt

            new_lines.append(new_line)
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

with open(output_bms, "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print(f"완료! 수정된 BMS는 '{output_bms}'에 저장되었습니다.")
