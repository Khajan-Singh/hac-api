from flask import Flask, request, jsonify
import requests
from lxml import html
from bs4 import BeautifulSoup
import pandas as pd
import re
import math

app = Flask(__name__)

green = ["#18FD73", "#ABFFB1"]
blue = ["#43B9FD", "#93D7FF"]
yellow = ["#FFCA63", "#FAF392"]
red = ["#F48A8A", "#F6ADAD"]

# Invalid Credentials Error
class Invalid_Credentials(Exception):
    def __init__(self):
        super().__init__("Set the username and password to valid values!")

class Account:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session_requests = requests.session()

        login_url = 'https://hac.friscoisd.org/HomeAccess/Account/LogOn?ReturnUrl=%2fHomeAccess%2f'
        result = self.session_requests.get(login_url)
        tree = html.fromstring(result.text)
        authenticity_token = list(set(tree.xpath("//input[@name='__RequestVerificationToken']/@value")))[0]

        self.login_payload = {
            "VerificationOption": "UsernamePassword",
            "Database": "10",
            "LogOnDetails.Password": password,
            "__RequestVerificationToken": authenticity_token,
            "LogOnDetails.UserName": username
        }
        login_result = self.session_requests.post(login_url, data=self.login_payload, headers=dict(referer=login_url))
        
        # Checking if the credentials are correct for seeing if the login button is in the output
        parser = BeautifulSoup(login_result.text, 'html.parser')
        element = parser.find('div', class_='sg-login-sign-in')

        # Check if the element exists
        if element:
            self.username = None
            self.password = None
            self.session_requests = None
            result = None
            login_result = None
            raise Invalid_Credentials

    def reset(self):
        self.__init__(self.username, self.password)

    # Function to initialize classes
    def _initialize_classes(self, grades_html, names_html):
        class1 = 0
        try:
            class1 = str(grades_html[0])
        except:
            pass
        return class1
    
    def return_student_gpas(self):
        urls = "https://hac.friscoisd.org/HomeAccess/Content/Student/Transcript.aspx"
        result = self.session_requests.get(urls, headers=dict(referer=urls))

        parser = BeautifulSoup(result.content, 'html.parser')

        weighted_gpa_element = parser.find('span', id='plnMain_rpTranscriptGroup_lblGPACum1')
        unweighted_gpa_element = parser.find('span', id='plnMain_rpTranscriptGroup_lblGPACum2')
        class_rank_element = parser.find('span', id='plnMain_rpTranscriptGroup_lblGPARank1')

        weighted_gpa = weighted_gpa_element.text if weighted_gpa_element else "N/A"
        unweighted_gpa = unweighted_gpa_element.text if unweighted_gpa_element else "N/A"
        class_rank = class_rank_element.text if class_rank_element else "N/A"
        class_percentile = "N/A"
        
        student_rank = None

        if class_rank != "N/A":
            split = class_rank.split(" ")
            student_rank = int(split[0])
            class_size = int(split[2])

            class_percentile = (student_rank / class_size) * 100
            class_percentile = math.ceil(class_percentile * 100) / 100
            class_percentile = str(class_percentile)

        return [weighted_gpa, unweighted_gpa, class_rank, class_percentile]
    
    def return_student_info(self):
        urls = "https://hac.friscoisd.org/HomeAccess/Content/Student/Registration.aspx"
        result = self.session_requests.get(urls, headers=dict(referer=urls))

        parser = BeautifulSoup(result.content, 'html.parser')

        student_id_element = parser.find('span', id='plnMain_lblRegStudentID')
        student_name_element = parser.find('span', id='plnMain_lblRegStudentName')
        birth_date_element = parser.find('span', id='plnMain_lblBirthDate')
        counselor_element = parser.find('span', id='plnMain_lblCounselor')
        building_element = parser.find('span', id='plnMain_lblBuildingName')
        calendar_element = parser.find('span', id='plnMain_lblCalendar')
        grade_element = parser.find('span', id='plnMain_lblGrade')
        language_element = parser.find('span', id='plnMain_lblLanguage')

        student_id = student_id_element.text if student_id_element else "N/A"
        student_name = student_name_element.text if student_name_element else "N/A"
        birth_date = birth_date_element.text if birth_date_element else "N/A"
        counselor = counselor_element.text if counselor_element else "N/A"
        building = building_element.text if building_element else "N/A"
        calendar = calendar_element.text if calendar_element else "N/A"
        grade = grade_element.text if grade_element else "N/A"
        language = language_element.text if language_element else "N/A"

        name_list = student_name.split(" ")
        first_name = name_list[1]
        last_name = name_list[0]
        name_list.remove(last_name)
        last_name = last_name[:-1]
        student_name = ""
        for entry in name_list:
            student_name += entry
            student_name += " "
        student_name += last_name

        return [student_id, student_name, first_name, birth_date, counselor, building, calendar, grade, language]

    def return_student_transcript(self):
        urls = "https://hac.friscoisd.org/HomeAccess/Content/Student/Transcript.aspx"
        result = self.session_requests.get(urls, headers=dict(referer=urls))

        parser = BeautifulSoup(result.content, 'html.parser')

        transcriptGroup = parser.find_all("td", "sg-transcript-group")

        transcriptDetails = []
        for index, transcript in enumerate(transcriptGroup):
            parser = BeautifulSoup(f"<html><body>{transcript}</body></html>", "lxml")
            innerTables = parser.find_all('table')

            headerTable = innerTables[0]
            coursesTable = innerTables[1]
            totalCreditsTable = innerTables[2]

            parser = BeautifulSoup(f"<html><body>{headerTable}</body></html>", "lxml")

            yearsAttended = parser.find('span', id=f'plnMain_rpTranscriptGroup_lblYearValue_{index}')
            gradeLevel = parser.find('span', id=f'plnMain_rpTranscriptGroup_lblGradeValue_{index}')
            building = parser.find('span', id=f'plnMain_rpTranscriptGroup_lblBuildingValue_{index}')

            yearsAttended = yearsAttended.text.strip() if yearsAttended else "N/A"
            gradeLevel = gradeLevel.text.strip() if gradeLevel else "N/A"
            building = building.text.strip() if building else "N/A"

            # Extract course details
            parser = BeautifulSoup(f"<html><body>{coursesTable}</body></html>", "lxml")
            courses = []
            rows = parser.find_all('tr', class_='sg-asp-table-data-row')
            for row in rows:
                columns = row.find_all('td')
                if len(columns) >= 6:
                    course = {
                        'courseCode': columns[0].text.strip() if columns[0] else "N/A",
                        'courseName': columns[1].text.strip() if columns[1] else "N/A",
                        'sem1Grade': columns[2].text.strip() if columns[2] else "N/A",
                        'sem2Grade': columns[3].text.strip() if columns[3] else "N/A",
                        'finalGrade': columns[4].text.strip() if columns[4] else "N/A",
                        'courseCredits': columns[5].text.strip() if columns[5] else "N/A"
                    }
                    courses.append(course)

            parser = BeautifulSoup(f"<html><body>{totalCreditsTable}</body></html>", "lxml")
            totalCredits_el = parser.find('label', id=f'plnMain_rpTranscriptGroup_LblTCreditValue_{index}')
            totalCredits = totalCredits_el.text if totalCredits_el else "N/A"

            transcriptDetails.append({
                'yearsAttended': yearsAttended,
                'gradeLevel': gradeLevel,
                'building': building,
                'totalCredits': totalCredits,
                'courses': courses
            })

        return transcriptDetails

    def get_username(self):
        return self.username

@app.route('/login', methods=['GET'])
def login():
    username = request.args.get('username')
    password = request.args.get('password')

    try:
        account = Account(username, password)
        return jsonify({"message": "Login successful", "username": account.get_username()}), 200
    except Invalid_Credentials:
        return jsonify({"message": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"message": f"An error occurred: {e}"}), 500

@app.route('/student_gpas', methods=['GET'])
def student_gpas():
    username = request.args.get('username')
    password = request.args.get('password')

    try:
        account = Account(username, password)
        info = account.return_student_gpas()
        return jsonify({"weightedGPA": info[0], "unweightedGPA": info[1], "rank": info[2], "percentile": info[3]}), 200
    except Invalid_Credentials:
        return jsonify({"message": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"message": f"An error occurred: {e}"}), 500

@app.route('/student_info', methods=['GET'])
def student_info():
    username = request.args.get('username')
    password = request.args.get('password')

    try:
        account = Account(username, password)
        info = account.return_student_info()
        return jsonify({"id": info[0], "name": info[1], "firstName": info[2], "birthdate": info[3], "counselor": info[4], "campus": info[5], "calendar": info[6], "grade": info[7], "language": info[8]}), 200
    except Invalid_Credentials:
        return jsonify({"message": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"message": f"An error occurred: {e}"}), 500

@app.route('/transcript', methods=["GET"])
def transcript():
    username = request.args.get('username')
    password = request.args.get('password')

    try:
        account = Account(username, password)
        transcript_info = account.return_student_transcript()
        gpa_info = account.return_student_gpas()
        return jsonify({
            "studentTranscript": transcript_info,
            "studentGPAs": {
                "weightedGPA": gpa_info[0],
                "unweightedGPA": gpa_info[1],
                "rank": gpa_info[2],
                "percentile": gpa_info[3]
            }
        })
    except Invalid_Credentials:
        return jsonify({"message": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"message": f"An error occurred: {e}"}), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5002, debug=True)
