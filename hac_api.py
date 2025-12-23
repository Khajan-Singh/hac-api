from flask import Flask, request, jsonify
import requests
from lxml import html
from bs4 import BeautifulSoup
import math
import time
import uuid
import threading

app = Flask(__name__)

# ---------- Config ----------
TOKEN_TTL_SECONDS = 30 * 60  # 30 minutes
CLEANUP_INTERVAL_SECONDS = 60

# token -> {account, expires_at}
_TOKEN_STORE = {}
_TOKEN_LOCK = threading.Lock()


# ---------- Exceptions ----------
class Invalid_Credentials(Exception):
    def __init__(self):
        super().__init__("Set the username and password to valid values!")


# ---------- HAC Account ----------
class Account:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session_requests = requests.session()

        login_url = "https://hac.friscoisd.org/HomeAccess/Account/LogOn?ReturnUrl=%2fHomeAccess%2f"
        result = self.session_requests.get(login_url)
        tree = html.fromstring(result.text)
        authenticity_token = list(
            set(tree.xpath("//input[@name='__RequestVerificationToken']/@value"))
        )[0]

        payload = {
            "VerificationOption": "UsernamePassword",
            "Database": "10",
            "LogOnDetails.Password": password,
            "__RequestVerificationToken": authenticity_token,
            "LogOnDetails.UserName": username,
        }

        login_result = self.session_requests.post(
            login_url, data=payload, headers={"referer": login_url}
        )

        parser = BeautifulSoup(login_result.text, "html.parser")
        if parser.find("div", class_="sg-login-sign-in"):
            raise Invalid_Credentials

    def return_student_gpas(self):
        url = "https://hac.friscoisd.org/HomeAccess/Content/Student/Transcript.aspx"
        r = self.session_requests.get(url, headers={"referer": url})
        soup = BeautifulSoup(r.content, "html.parser")

        weighted = soup.find("span", id="plnMain_rpTranscriptGroup_lblGPACum1")
        unweighted = soup.find("span", id="plnMain_rpTranscriptGroup_lblGPACum2")
        rank_el = soup.find("span", id="plnMain_rpTranscriptGroup_lblGPARank1")

        weighted = weighted.text if weighted else "N/A"
        unweighted = unweighted.text if unweighted else "N/A"
        rank = rank_el.text if rank_el else "N/A"
        percentile = "N/A"

        if rank != "N/A":
            r, _, size = rank.split(" ")
            percentile = math.ceil((int(r) / int(size)) * 10000) / 100

        return [weighted, unweighted, rank, str(percentile)]

    def return_student_info(self):
        url = "https://hac.friscoisd.org/HomeAccess/Content/Student/Registration.aspx"
        r = self.session_requests.get(url, headers={"referer": url})
        soup = BeautifulSoup(r.content, "html.parser")

        def grab(id):
            el = soup.find("span", id=id)
            return el.text if el else "N/A"

        student_name = grab("plnMain_lblRegStudentName")
        parts = student_name.split(" ")
        first = parts[1] if len(parts) > 1 else "N/A"
        last = parts[0].rstrip(",")

        full_name = " ".join(parts[1:]) + " " + last

        return [
            grab("plnMain_lblRegStudentID"),
            full_name.strip(),
            first,
            grab("plnMain_lblBirthDate"),
            grab("plnMain_lblCounselor"),
            grab("plnMain_lblBuildingName"),
            grab("plnMain_lblCalendar"),
            grab("plnMain_lblGrade"),
            grab("plnMain_lblLanguage"),
        ]

    def return_student_transcript(self):
        url = "https://hac.friscoisd.org/HomeAccess/Content/Student/Transcript.aspx"
        r = self.session_requests.get(url, headers={"referer": url})
        soup = BeautifulSoup(r.content, "html.parser")

        groups = soup.find_all("td", class_="sg-transcript-group")
        transcript = []

        for i, group in enumerate(groups):
            p = BeautifulSoup(str(group), "lxml")
            tables = p.find_all("table")

            header, courses_tbl, credits_tbl = tables[:3]

            hp = BeautifulSoup(str(header), "lxml")
            years = hp.find("span", id=f"plnMain_rpTranscriptGroup_lblYearValue_{i}")
            grade = hp.find("span", id=f"plnMain_rpTranscriptGroup_lblGradeValue_{i}")
            building = hp.find("span", id=f"plnMain_rpTranscriptGroup_lblBuildingValue_{i}")

            cp = BeautifulSoup(str(courses_tbl), "lxml")
            courses = []

            for row in cp.find_all("tr", class_="sg-asp-table-data-row"):
                cols = row.find_all("td")
                if len(cols) >= 6:
                    courses.append({
                        "courseCode": cols[0].text.strip(),
                        "courseName": cols[1].text.strip(),
                        "sem1Grade": cols[2].text.strip(),
                        "sem2Grade": cols[3].text.strip(),
                        "finalGrade": cols[4].text.strip(),
                        "courseCredits": cols[5].text.strip(),
                    })

            tp = BeautifulSoup(str(credits_tbl), "lxml")
            credits = tp.find("label", id=f"plnMain_rpTranscriptGroup_LblTCreditValue_{i}")

            transcript.append({
                "yearsAttended": years.text if years else "N/A",
                "gradeLevel": grade.text if grade else "N/A",
                "building": building.text if building else "N/A",
                "totalCredits": credits.text if credits else "N/A",
                "courses": courses,
            })

        return transcript


# ---------- Token helpers ----------
def _get_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.split(" ", 1)[1]
    return None


def _get_account():
    token = _get_token()
    if not token:
        return None, ("Missing Authorization header", 401)

    with _TOKEN_LOCK:
        entry = _TOKEN_STORE.get(token)
        if not entry or entry["expires_at"] < time.time():
            return None, ("Invalid or expired token", 401)
        entry["expires_at"] = time.time() + TOKEN_TTL_SECONDS
        return entry["account"], None


def _cleanup_loop():
    while True:
        time.sleep(CLEANUP_INTERVAL_SECONDS)
        with _TOKEN_LOCK:
            now = time.time()
            for t in list(_TOKEN_STORE):
                if _TOKEN_STORE[t]["expires_at"] < now:
                    del _TOKEN_STORE[t]


threading.Thread(target=_cleanup_loop, daemon=True).start()


# ---------- Routes ----------
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    try:
        acc = Account(data.get("username"), data.get("password"))
        token = uuid.uuid4().hex
        with _TOKEN_LOCK:
            _TOKEN_STORE[token] = {
                "account": acc,
                "expires_at": time.time() + TOKEN_TTL_SECONDS,
            }
        return jsonify({
            "message": "Login successful",
            "username": data.get("username"),
            "token": token,
            "expiresIn": TOKEN_TTL_SECONDS,
        })
    except Invalid_Credentials:
        return jsonify({"message": "Invalid credentials"}), 401


@app.route("/student_gpas")
def student_gpas():
    acc, err = _get_account()
    if err:
        return jsonify({"message": err[0]}), err[1]
    g = acc.return_student_gpas()
    return jsonify({
        "weightedGPA": g[0],
        "unweightedGPA": g[1],
        "rank": g[2],
        "percentile": g[3],
    })


@app.route("/student_info")
def student_info():
    acc, err = _get_account()
    if err:
        return jsonify({"message": err[0]}), err[1]
    i = acc.return_student_info()
    return jsonify({
        "id": i[0],
        "name": i[1],
        "firstName": i[2],
        "birthdate": i[3],
        "counselor": i[4],
        "campus": i[5],
        "calendar": i[6],
        "grade": i[7],
        "language": i[8],
    })


@app.route("/transcript")
def transcript():
    acc, err = _get_account()
    if err:
        return jsonify({"message": err[0]}), err[1]

    t = acc.return_student_transcript()
    g = acc.return_student_gpas()

    return jsonify({
        "studentTranscript": t,
        "studentGPAs": {
            "weightedGPA": g[0],
            "unweightedGPA": g[1],
            "rank": g[2],
            "percentile": g[3],
        },
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=False)
