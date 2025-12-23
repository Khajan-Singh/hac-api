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
            totalCredits = parser.find('label', id=f'plnMain_rpTranscriptGroup_LblTCreditValue_{index}').text

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
        return jsonify({"studentTranscript": transcript_info, "studentGPAs": {"weightedGPA": gpa_info[0], "unweightedGPA": gpa_info[1], "rank": gpa_info[2], "percentile": gpa_info[3]}})
    except Invalid_Credentials:
        return jsonify({"message": "Invalid credentials"}), 401
    except Exception as e:
        return jsonify({"message": f"An error occurred: {e}"}), 500

@app.route('/current_grades', methods=["GET"])
def current_grades():
    return jsonify({"currentClasses": [{"name": "CATE27600B - 3 Mobile App Programming S2@CTEC","grade": "","weight": "6","credits": "1","lastUpdated": "","assignments": []},{"name": "CATE36400B - 1 Prac News Prod 2 S2","grade": "","weight": "5","credits": "1","lastUpdated": "1/6/2022","assignments": [{"name": "PA Script #3","category": "Minor Grades","dateAssigned": "02/09/2022","dateDue": "03/04/2022","score": "","totalPoints": "100.00"},{"name": "Social Media Posts","category": "Minor Grades","dateAssigned": "01/04/2022","dateDue": "03/02/2022","score": "","totalPoints": "100.00"},{"name": "MP3 Package/Segment #2","category": "Major Grades","dateAssigned": "01/10/2022","dateDue": "03/02/2022","score": "","totalPoints": "100.00"},{"name": "Event Coverage","category": "Major Grades","dateAssigned": "01/04/2022","dateDue": "02/25/2022","score": "","totalPoints": "100.00"},{"name": "PA Script #2","category": "Minor Grades","dateAssigned": "01/24/2022","dateDue": "02/08/2022","score": "","totalPoints": "100.00"},{"name": "MP3 Package/Segment #1","category": "Major Grades","dateAssigned": "01/11/2022","dateDue": "02/04/2022","score": "","totalPoints": "100.00"},{"name": "PA Script #1","category": "Minor Grades","dateAssigned": "01/04/2022","dateDue": "01/21/2022","score": "97.00","totalPoints": "100.00"},{"name": "MP3 Calendar Check","category": "Non-graded","dateAssigned": "01/04/2022","dateDue": "01/06/2022","score": "100.0","totalPoints": "100.00"}]},{"name": "ELA14300B - 4 AP English Literature S2","grade": "85.00","weight": "6","credits": "1","lastUpdated": "1/13/2022","assignments": [{"name": "Thesis Practice #1","category": "Minor Grades","dateAssigned": "","dateDue": "01/13/2022","score": "90.00","totalPoints": "100.00"},{"name": "Christmas Carol Q3 Essay","category": "Minor Grades","dateAssigned": "","dateDue": "01/05/2022","score": "80.00","totalPoints": "100.00"}]},{"name": "MTH45300B - 1 AP Calculus AB S2","grade": "80.80","weight": "6","credits": "1","lastUpdated": "1/10/2022","assignments": [{"name": "Unit 6 Test (Integration)","category": "Major Grades","dateAssigned": "","dateDue": "02/08/2022","score": "","totalPoints": "100.00"},{"name": "Delta Math Practice (Unit 6)","category": "Minor Grades","dateAssigned": "","dateDue": "02/08/2022","score": "","totalPoints": "100.00"},{"name": "Quiz 4 (Antiderivatives and Rules of Integration)","category": "Minor Grades","dateAssigned": "","dateDue": "01/31/2022","score": "","totalPoints": "100.00"},{"name": "Quiz 3 (FTC and Definite Integrals)","category": "Minor Grades","dateAssigned": "","dateDue": "01/27/2022","score": "","totalPoints": "100.00"},{"name": "Quiz 2 (Properties of Def. Integrals)","category": "Minor Grades","dateAssigned": "","dateDue": "01/25/2022","score": "","totalPoints": "100.00"},{"name": "Quiz 1 (Reimann Sums and Definite Integrals)","category": "Minor Grades","dateAssigned": "","dateDue": "01/19/2022","score": "","totalPoints": "100.00"},{"name": "Unit 5 Test (Analytical Applications of Derivatives)","category": "Major Grades","dateAssigned": "","dateDue": "01/10/2022","score": "78.00","totalPoints": "100.00"},{"name": "Delta Math Practice (Unit 5)","category": "Minor Grades","dateAssigned": "","dateDue": "01/10/2022","score": "85.00","totalPoints": "100.00"}]},{"name": "MTH45310B - 4 AP Statistics S2","grade": "0.00","weight": "6","credits": "1","lastUpdated": "","assignments": [{"name": "Test - 8 Confidence Intervals","category": "Major Grades","dateAssigned": "","dateDue": "01/26/2022","score": "","totalPoints": "100.00"},{"name": "Skills Check - 8 Confidence Intervals","category": "Minor Grades","dateAssigned": "","dateDue": "01/24/2022","score": "","totalPoints": "100.00"},{"name": "Practice - 8.3 (canvas)","category": "Non-graded","dateAssigned": "","dateDue": "01/24/2022","score": "","totalPoints": "100.00"},{"name": "Practice - 8.2 (canvas)","category": "Non-graded","dateAssigned": "","dateDue": "01/24/2022","score": "","totalPoints": "100.00"},{"name": "Practice - 8.1 (canvas)","category": "Non-graded","dateAssigned": "","dateDue": "01/24/2022","score": "","totalPoints": "100.00"},{"name": "Group Skills Check - 7 Sampling Distributions","category": "Minor Grades","dateAssigned": "","dateDue": "01/11/2022","score": "","totalPoints": "50.00"}]},{"name": "SCI43300B - 1 AP Environmental Science S2","grade": "","weight": "6","credits": "1","lastUpdated": "","assignments": []},{"name": "SST34300 - 4 AP Government","grade": "0.00","weight": "6","credits": "1","lastUpdated": "","assignments": [{"name": "Midterm Exam (Units 1 & 2)","category": "Major Grades","dateAssigned": "","dateDue": "02/23/2022","score": "","totalPoints": "100.00"},{"name": "Unit 2 Major Grade FRQ","category": "Major Grades","dateAssigned": "","dateDue": "02/16/2022","score": "","totalPoints": "100.00"},{"name": "Unit 2 MC Quiz","category": "Minor Grades","dateAssigned": "","dateDue": "02/14/2022","score": "","totalPoints": "100.00"},{"name": "Unit 2 Argument FRQ Practice","category": "Minor Grades","dateAssigned": "","dateDue": "02/11/2022","score": "","totalPoints": "100.00"},{"name": "Unit 2 Congress FRQ Practice","category": "Minor Grades","dateAssigned": "","dateDue": "02/04/2022","score": "","totalPoints": "100.00"},{"name": "Unit 1 Major Grade FRQ","category": "Major Grades","dateAssigned": "","dateDue": "01/21/2022","score": "","totalPoints": "100.00"},{"name": "Unit 1 MC Quiz","category": "Minor Grades","dateAssigned": "","dateDue": "01/21/2022","score": "","totalPoints": "100.00"},{"name": "Unit 1 Concept Application & Argument FRQ Practice","category": "Minor Grades","dateAssigned": "","dateDue": "01/14/2022","score": "","totalPoints": "100.00"}]}]})

@app.route('/past_grades', methods=["GET"])
def past_grades():
    return jsonify({"pastClasses": [{"lastUpdated": "12/17/2021","assignments": [{"name": "Loops and lists","category": "Major Grades","dateAssigned": "","dateDue": "10/12/2021","score": "100.0","totalPoints": "100.00"},{"name": "Loops","category": "Minor Grades","dateAssigned": "","dateDue": "10/04/2021","score": "CWS","totalPoints": "100.00"},{"name": "Collections","category": "Minor Grades","dateAssigned": "","dateDue": "09/30/2021","score": "100.0","totalPoints": "100.00"},{"name": "Classes and structures","category": "Major Grades","dateAssigned": "","dateDue": "08/27/2021","score": "100.0","totalPoints": "100.00"},{"name": "Programmatically creating UI components","category": "Minor Grades","dateAssigned": "","dateDue": "08/27/2021","score": "100.0","totalPoints": "100.00"},{"name": "Creating simple UI components","category": "Minor Grades","dateAssigned": "","dateDue": "08/27/2021","score": "100.0","totalPoints": "100.00"},{"name": "Introductory Swift","category": "Minor Grades","dateAssigned": "","dateDue": "08/19/2021","score": "CWS","totalPoints": "100.00"},{"name": "App dev cycle","category": "Minor Grades","dateAssigned": "","dateDue": "08/17/2021","score": "100.00","totalPoints": "100.00"}],"credits": "1","grade": "100.0","color1": green[0],"color2": green[1],"name": "Mobile App Programming S1@CTEC","id": "CATE27600A - 3","weight": "6"},{"lastUpdated": "12/26/2021","assignments": [{"name": "MP2 Package/Segment","category": "Major Grades","dateAssigned": "09/27/2021","dateDue": "10/15/2021","score": "83.00","totalPoints": "100.00"},{"name": "PA Script #4","category": "Minor Grades","dateAssigned": "09/24/2021","dateDue": "10/15/2021","score": "95.00","totalPoints": "100.00"},{"name": "Show Elements (Show Open, Graphics, etc)","category": "Minor Grades","dateAssigned": "08/16/2021","dateDue": "10/15/2021","score": "100.0","totalPoints": "100.00"},{"name": "Social Media Post #2","category": "Minor Grades","dateAssigned": "09/27/2021","dateDue": "10/15/2021","score": "91.00","totalPoints": "100.00"},{"name": "PA Script #3","category": "Minor Grades","dateAssigned": "09/20/2021","dateDue": "10/15/2021","score": "89.00","totalPoints": "100.00"},{"name": "Event Coverage","category": "Major Grades","dateAssigned": "08/12/2021","dateDue": "10/07/2021","score": "60.00","totalPoints": "100.00"},{"name": "MP1 Package/Segment #1","category": "Major Grades","dateAssigned": "08/16/2021","dateDue": "09/24/2021","score": "97.00","totalPoints": "100.00"},{"name": "Social Media Post #1","category": "Minor Grades","dateAssigned": "08/24/2021","dateDue": "09/24/2021","score": "98.00","totalPoints": "100.00"},{"name": "PA Script #2","category": "Minor Grades","dateAssigned": "09/01/2021","dateDue": "09/17/2021","score": "93.00","totalPoints": "100.00"},{"name": "PA Script #1","category": "Minor Grades","dateAssigned": "08/12/2021","dateDue": "08/31/2021","score": "100.0","totalPoints": "100.00"},{"name": "Practicum Training Plan","category": "Minor Grades","dateAssigned": "08/12/2021","dateDue": "08/26/2021","score": "100.0","totalPoints": "100.00"},{"name": "MP1 Calendar Check","category": "Non-graded","dateAssigned": "08/12/2021","dateDue": "08/16/2021","score": "100.0","totalPoints": "100.00"}],"credits": "1","grade": "72.94","color1": yellow[0],"color2": yellow[1],"name": "Prac News Prod 2 S1","id": "CATE36400A - 1","weight": "5"},{"lastUpdated": "12/17/2021","assignments": [{"name": "Timed Write #2","category": "Major Grades","dateAssigned": "","dateDue": "10/05/2021","score": "85.00","totalPoints": "100.00"},{"name": "Macbeth Soliloquy","category": "Minor Grades","dateAssigned": "","dateDue": "10/04/2021","score": "85.00","totalPoints": "100.00"},{"name": "College Essay","category": "Major Grades","dateAssigned": "","dateDue": "09/17/2021","score": "85.00","totalPoints": "100.00"},{"name": "Macbeth Quiz","category": "Minor Grades","dateAssigned": "","dateDue": "09/14/2021","score": "92.00","totalPoints": "100.00"},{"name": "Macbeth Timed Writing","category": "Minor Grades","dateAssigned": "","dateDue": "09/01/2021","score": "80.00","totalPoints": "100.00"},{"name": "College Essay OUTLINE, 10C","category": "Minor Grades","dateAssigned": "08/27/2021","dateDue": "08/27/2021","score": "100.0","totalPoints": "100.00"},{"name": "Macbeth Pre-Reading Questions, 4F","category": "Minor Grades","dateAssigned": "","dateDue": "08/20/2021","score": "80.00","totalPoints": "100.00"},{"name": "Intro Letter, 9E","category": "Minor Grades","dateAssigned": "","dateDue": "08/12/2021","score": "100.0","totalPoints": "100.00"}],"credits": "1","grade": "58.46","color1": red[0],"color2": red[1],"name": "AP English Literature S1","id": "ELA14300A - 4","weight": "6"},{"lastUpdated": "12/8/2021","assignments": [{"name": "Unit 2 Test (Limit Def'n of Deriv, Basic Derivative Rules)","category": "Major Grades","dateAssigned": "","dateDue": "10/07/2021","score": "85.00","totalPoints": "100.00"},{"name": "2.4,2.6 Delta Math Practice","category": "Minor Grades","dateAssigned": "","dateDue": "10/05/2021","score": "94.00","totalPoints": "100.00"},{"name": "2.3,2.5 Delta Math Practice","category": "Minor Grades","dateAssigned": "","dateDue": "09/24/2021","score": "96.00","totalPoints": "100.00"},{"name": "2.1-2.2 Delta Math Practice","category": "Minor Grades","dateAssigned": "","dateDue": "09/20/2021","score": "100.0","totalPoints": "100.00"},{"name": "Unit 1 Test (Limits)","category": "Major Grades","dateAssigned": "","dateDue": "09/09/2021","score": "83.00","totalPoints": "100.00"},{"name": "1.7-1.8 Delta Math Average","category": "Minor Grades","dateAssigned": "","dateDue": "09/01/2021","score": "90.00","totalPoints": "100.00"},{"name": "1.4-1.6 Delta Math Practice","category": "Minor Grades","dateAssigned": "","dateDue": "08/30/2021","score": "100.0","totalPoints": "100.00"},{"name": "1.1-1.3 Delta Math Average","category": "Minor Grades","dateAssigned": "","dateDue": "08/20/2021","score": "89.00","totalPoints": "100.00"},{"name": "1.2 Skills Check (Limits Graphically)","category": "Minor Grades","dateAssigned": "","dateDue": "08/16/2021","score": "100.0","totalPoints": "100.00"}],"credits": "1","grade": "88.63","color1": blue[0],"color2": blue[1],"name": "AP Calculus AB S1","id": "MTH45300A - 1","weight": "6"},{"lastUpdated": "12/17/2021","assignments": [{"name": "Test - 3.2 Least Squares Regression","category": "Major Grades","dateAssigned": "","dateDue": "10/07/2021","score": "71.00","totalPoints": "100.00"},{"name": "Test - 3.1 Scatterplots and Correlation","category": "Major Grades","dateAssigned": "","dateDue": "10/07/2021","score": "71.00","totalPoints": "100.00"},{"name": "Review - 3 Describing Relationships","category": "Non-graded","dateAssigned": "","dateDue": "10/07/2021","score": "58.00","totalPoints": "100.00"},{"name": "Skills Check - 3.2 LSRL, Residuals, and Residual Plots","category": "Minor Grades","dateAssigned": "","dateDue": "10/04/2021","score": "89.00","totalPoints": "100.00"},{"name": "Skills Check - 3.1 Scatterplots and Correlation","category": "Minor Grades","dateAssigned": "","dateDue": "09/30/2021","score": "79.00","totalPoints": "100.00"},{"name": "Test - 2.2 Normal Distributions","category": "Major Grades","dateAssigned": "","dateDue": "09/24/2021","score": "100.0","totalPoints": "100.00"},{"name": "Test - 2.1 Describing Location","category": "Major Grades","dateAssigned": "","dateDue": "09/24/2021","score": "92.00","totalPoints": "100.00"},{"name": "Review - 2 Modeling Distributions of Data","category": "Non-graded","dateAssigned": "","dateDue": "09/24/2021","score": "91.00","totalPoints": "100.00"},{"name": "Skills Check - 2.2 Density Curves and Normal Distributions","category": "Minor Grades","dateAssigned": "","dateDue": "09/20/2021","score": "100.0","totalPoints": "100.00"},{"name": "Practice - 2.2 Normal Distributions","category": "Non-graded","dateAssigned": "","dateDue": "09/20/2021","score": "L","totalPoints": "100.00"},{"name": "Practice - 2.2 Density Curves and the Empirical Rule","category": "Non-graded","dateAssigned": "","dateDue": "09/20/2021","score": "60.00","totalPoints": "100.00"},{"name": "Skills Check - 2.1 Describing Location","category": "Minor Grades","dateAssigned": "","dateDue": "09/16/2021","score": "92.00","totalPoints": "100.00"},{"name": "Practice - 2.1","category": "Non-graded","dateAssigned": "","dateDue": "09/16/2021","score": "100.0","totalPoints": "100.00"},{"name": "Test - 1 Exploring Data","category": "Major Grades","dateAssigned": "","dateDue": "09/08/2021","score": "89.00","totalPoints": "100.00"},{"name": "Quiz - 1 Exploring Data","category": "Minor Grades","dateAssigned": "","dateDue": "09/02/2021","score": "89.00","totalPoints": "100.00"},{"name": "Skills Check - 1.1 Analyzing Categorical Data","category": "Minor Grades","dateAssigned": "","dateDue": "08/23/2021","score": "100.0","totalPoints": "100.00"}],"credits": "1","grade": "87.37","color1": blue[0],"color2": blue[1],"name": "AP Statistics S1","id": "MTH45310A - 4","weight": "6"},{"lastUpdated": "12/17/2021","assignments": [{"name": "Unit 2 Assessment - Biodiversity_all topics","category": "Major Grades","dateAssigned": "","dateDue": "10/13/2021","score": "86.67","totalPoints": "100.00"},{"name": "Unit 2 QUIZ - Topics 2.1-2.3","category": "Minor Grades","dateAssigned": "","dateDue": "10/06/2021","score": "86.67","totalPoints": "100.00"},{"name": "Unit 2 - Island Biogeography Lab","category": "Minor Grades","dateAssigned": "","dateDue": "10/04/2021","score": "100.0","totalPoints": "100.00"},{"name": "Unit 1 - Ecosystem project","category": "Minor Grades","dateAssigned": "","dateDue": "09/24/2021","score": "100.0","totalPoints": "100.00"},{"name": "Unit 1 Assessment - all Topics","category": "Major Grades","dateAssigned": "","dateDue": "09/22/2021","score": "91.67","totalPoints": "100.00"},{"name": "Unit 1 - Topics 1.8-1.11 QUIZ","category": "Minor Grades","dateAssigned": "","dateDue": "09/16/2021","score": "93.00","totalPoints": "100.00"},{"name": "Owl Pellet Lab- Flow of Energy","category": "Minor Grades","dateAssigned": "","dateDue": "09/16/2021","score": "97.00","totalPoints": "100.00"},{"name": "Unit 1 - Topics 1.4-1.7 QUIZ (BGC cycles)","category": "Minor Grades","dateAssigned": "","dateDue": "09/02/2021","score": "95.00","totalPoints": "100.00"},{"name": "Bozeman- BGC Cycles Performance Task","category": "Minor Grades","dateAssigned": "","dateDue": "09/02/2021","score": "96.00","totalPoints": "100.00"},{"name": "Unit 1 - Topics 1.1 - 1.3 QUIZ","category": "Minor Grades","dateAssigned": "","dateDue": "08/25/2021","score": "91.67","totalPoints": "100.00"}],"credits": "1","grade": "91.47","color1": green[0],"color2": green[1],"name": "AP Environmental Science S1","id": "SCI43300A - 1","weight": "6"},{"lastUpdated": "12/10/2021","assignments": [{"name": "Units 1-3 FRQ Test: Choice #2","category": "Major Grades","dateAssigned": "","dateDue": "09/27/2021","score": "88.00","totalPoints": "100.00"},{"name": "Units 1-3 FRQ Test: Choice #1","category": "Major Grades","dateAssigned": "","dateDue": "09/27/2021","score": "100.0","totalPoints": "100.00"},{"name": "Units 1-3 FRQ Test: Required Question","category": "Major Grades","dateAssigned": "","dateDue": "09/27/2021","score": "100.0","totalPoints": "100.00"},{"name": "Units 1-3 MCQ Test: Unit 3 Topic","category": "Major Grades","dateAssigned": "","dateDue": "09/27/2021","score": "94.00","totalPoints": "100.00"},{"name": "Units 1-3 MCQ Test: Unit 2 Topic","category": "Major Grades","dateAssigned": "","dateDue": "09/27/2021","score": "100.0","totalPoints": "100.00"},{"name": "Units 1-3 MCQ Test: Unit 1 Topic","category": "Major Grades","dateAssigned": "","dateDue": "09/27/2021","score": "79.00","totalPoints": "100.00"},{"name": "Unit 3 FRQ Quiz","category": "Minor Grades","dateAssigned": "","dateDue": "09/23/2021","score": "100.0","totalPoints": "100.00"},{"name": "Unit 3 MCQ Quiz","category": "Minor Grades","dateAssigned": "","dateDue": "09/23/2021","score": "96.00","totalPoints": "100.00"},{"name": "Unit 3 AP Classroom Progress Check MCQ","category": "Non-graded","dateAssigned": "","dateDue": "09/21/2021","score": "INS","totalPoints": "100.00"},{"name": "Flipped Video 3.5: Return to LRAS","category": "Non-graded","dateAssigned": "","dateDue": "09/17/2021","score": "INS","totalPoints": "100.00"},{"name": "Flipped Video 3.3: Fiscal Policy","category": "Non-graded","dateAssigned": "","dateDue": "09/15/2021","score": "INS","totalPoints": "100.00"},{"name": "Flipped Video 3.2: Potential Output and Gaps","category": "Non-graded","dateAssigned": "","dateDue": "09/13/2021","score": "CNS","totalPoints": "100.00"},{"name": "Flipped Video 3.1: AD/SRAS/LRAS","category": "Non-graded","dateAssigned": "","dateDue": "09/09/2021","score": "CNS","totalPoints": "100.00"},{"name": "Unit 2 FRQ Quiz","category": "Minor Grades","dateAssigned": "","dateDue": "09/09/2021","score": "100.0","totalPoints": "100.00"},{"name": "Unit 2 MCQ Quiz","category": "Minor Grades","dateAssigned": "","dateDue": "09/09/2021","score": "100.0","totalPoints": "100.00"},{"name": "Unit 2 AP Classroom Progress Check MCQ","category": "Non-graded","dateAssigned": "","dateDue": "09/07/2021","score": "CNS","totalPoints": "100.00"},{"name": "Flipped Video 2.4: Business Cycle","category": "Non-graded","dateAssigned": "","dateDue": "09/01/2021","score": "CNS","totalPoints": "100.00"},{"name": "Flipped Video 2.3: Inflation","category": "Non-graded","dateAssigned": "","dateDue": "09/01/2021","score": "CNS","totalPoints": "100.00"},{"name": "Flipped Video 2.2: Unemployment","category": "Non-graded","dateAssigned": "","dateDue": "08/30/2021","score": "CNS","totalPoints": "100.00"},{"name": "Flipped Video 2.1: Circular Flow and GDP","category": "Non-graded","dateAssigned": "","dateDue": "08/26/2021","score": "CNS","totalPoints": "100.00"},{"name": "Unit 1 FRQ Quiz","category": "Minor Grades","dateAssigned": "","dateDue": "08/26/2021","score": "100.0","totalPoints": "100.00"},{"name": "Unit 1 MCQ Quiz","category": "Minor Grades","dateAssigned": "","dateDue": "08/26/2021","score": "88.00","totalPoints": "100.00"},{"name": "Unit 1 AP Classroom Progress Check MCQ","category": "Non-graded","dateAssigned": "","dateDue": "08/24/2021","score": "CNS","totalPoints": "100.00"},{"name": "Flipped Video 1.4: Double Shifts & Disequilibrium","category": "Non-graded","dateAssigned": "","dateDue": "08/20/2021","score": "CNS","totalPoints": "100.00"},{"name": "Flipped Video 1.3: Micro Markets","category": "Non-graded","dateAssigned": "","dateDue": "08/18/2021","score": "CNS","totalPoints": "100.00"},{"name": "Flipped Video 1.2: Production Possibilities Curve","category": "Non-graded","dateAssigned": "","dateDue": "08/16/2021","score": "CNS","totalPoints": "100.00"},{"name": "Flipped Video 1.1: Scarcity","category": "Non-graded","dateAssigned": "","dateDue": "08/12/2021","score": "CNS","totalPoints": "100.00"}],"credits": "1","grade": "94.43","color1": green[0],"color2": green[1],"name": "AP Economics","id": "SST34310 - 3","weight": "6"}]})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5002, debug=True)
