# test_convert.py
import requests

BASE="http://127.0.0.1:8000"
FILES = {
  "raw": "test_csvs/sample_vendor_raw.csv",
  "b2b": "test_csvs/sample_b2b_like.csv",
  "mixed": "test_csvs/sample_mixed.csv",
}

def preview(path, manufacturer=None, force=False):
    with open(path, "rb") as fh:
        data = {}
        if manufacturer: data["manufacturer"] = manufacturer
        data["force_manufacturer"] = "true" if force else "false"
        res = requests.post(f"{BASE}/b2b/preview", files={"file": fh}, data=data)
        print("PREVIEW", path, res.status_code)
        print(res.json())

def convert(path, manufacturer=None, force=False, out="out.csv"):
    with open(path, "rb") as fh:
        data = {}
        if manufacturer: data["manufacturer"] = manufacturer
        data["force_manufacturer"] = "true" if force else "false"
        res = requests.post(f"{BASE}/b2b/convert-to-b2b", files={"file": fh}, data=data)
        print("CONVERT", path, res.status_code)
        if res.ok:
            with open(out, "wb") as outfh:
                outfh.write(res.content)
            print("Saved ->", out)

if __name__ == "__main__":
    preview(FILES["raw"], manufacturer="Acme Floors", force=False)
    convert(FILES["raw"], manufacturer="Acme Floors", force=True, out="converted_raw.csv")
    preview(FILES["mixed"])
    convert(FILES["mixed"], out="converted_mixed.csv")
