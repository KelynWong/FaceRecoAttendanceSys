# import the necessary packages
import face_recognition
import argparse
import pickle
import time
import cv2
import mysql.connector as mysql
from datetime import datetime
import json
from playsound import playsound

# initialize variables starting values
classID = 0
count = 0
confirmNameCount = 0
faceRecognised = False
done = False
name = ''
oldName = ''
present = 0

# config mysql connection
db = mysql.connect(
    host = "localhost",
    user = "root",
    passwd = "password",
    database = "facerecognitionattendancesystem"
)

# construct the argument parser and parse the arguments
ap = argparse.ArgumentParser()
ap.add_argument("-n", "--class", required=True, help = "class name")
ap.add_argument("-c", "--cascade", required=True, help = "path to where the face cascade resides")
ap.add_argument("-e", "--encodings", required=True,help="path to serialized db of facial encodings")
args = vars(ap.parse_args())

# load the known faces and embeddings along with OpenCV's Haarcascade for face detection
data = pickle.loads(open(args["encodings"], "rb").read())
detector = cv2.CascadeClassifier(args["cascade"])

# initialize the video stream and allow the camera sensor to warm up
# capture = VideoStream(src=0).start()
# capture = VideoStream(usePiCamera=True).start()
capture = cv2.VideoCapture(0) # if using computer webcam
time.sleep(2.0)

while True:
    className = args["class"]
    # check if className is valid
    cursor = db.cursor()
    query = 'SELECT ClassID FROM class WHERE name = "' + className + '"'
    cursor.execute(query)
    datas = cursor.fetchall()

    for record in datas:
        classID = record[0]

    # loop over frames from the video file stream
    if classID != 0:
        while True:
            # grab the frame from the threaded video stream and resize it to 500px (to speedup processing)
            rval, frame = capture.read()
                
            # convert the input frame from (1) BGR to grayscale (for face detection) and (2) from BGR to RGB (for face recognition)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
            # detect faces in the grayscale frame
            rects = detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
                
            # OpenCV returns bounding box coordinates in (x, y, w, h) order but we need them in (top, right, bottom, left) order, so we need to do a bit of reordering
            boxes = [(y, x + w, y + h, x) for (x, y, w, h) in rects]
                
            # compute the facial embeddings for each face bounding box
            encodings = face_recognition.face_encodings(rgb, boxes)
            names = []
            oldName = name
            # set name to be blank as this is to identify if there is even a face in the frame
            name = ''
            faceRecognised = False

            # if face is detected in the frame, loop over the facial embeddings
            for encoding in encodings:
                # attempt to match each face in the input image to our known encodings
                matches = face_recognition.compare_faces(data["encodings"], encoding)
                # set name to unknown as this is to identify if face is recognized or not
                name = "Unknown"
                
                # if face is recognized
                if True in matches:
                    # find the indexes of all matched faces then initialize a dictionary to count the total number of times each face was matched
                    matchedIdxs = [i for (i, b) in enumerate(matches) if b]
                    counts = {}
                    # loop over the matched indexes and maintain a count for each recognized face face
                    for i in matchedIdxs:
                        name = data["names"][i]
                        counts[name] = counts.get(name, 0) + 1
                        
                    # determine the recognized face with the largest number of votes (note: in the event of an unlikely tie Python will select first entry in the dictionary)
                    name = max(counts, key=counts.get)
                        
                # update the list of names
                names.append(name)

            # loop over the recognized faces
            for ((top, right, bottom, left), name) in zip(boxes, names):
                # draw the predicted face name on the image
                cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                y = top - 15 if top - 15 > 15 else top + 15
                cv2.putText(frame, name, (left, y), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (0, 255, 0), 2)
                faceRecognised = True
                if oldName == name:
                    confirmNameCount = confirmNameCount + 1
                    confirmedName = name
                    break

            if name == '':
                cv2.putText(frame, 'Please position your face in front of the camera', (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2, cv2.LINE_AA)

            if confirmNameCount == 5 and faceRecognised == True:
                # get the studentID from database
                cursor = db.cursor()
                query = "SELECT DISTINCT student.StudentID FROM classattendance INNER JOIN student ON classattendance.StudentID = student.StudentID WHERE Name = '{}' AND ClassID={};".format(confirmedName, classID)
                cursor.execute(query)
                datas = cursor.fetchall()
                
                if len(datas) != 0 :
                    for record in datas:
                        studentID = record[0]

                    # record into the database that this student is present for the class
                    cursor = db.cursor()
                    query = "UPDATE classattendance SET Present = 1, DateTime=%s WHERE ClassID = %s AND StudentID = %s"
                    values = (datetime.now(), classID, studentID)
                    cursor.execute(query,values)
                    db.commit()
                    present = 1
                    cv2.circle(frame, (550, 50), 20, (0, 255, 0), -1)
                    playsound('C:\\Users\\kelyn\\Downloads\\faceRecognitionAttendanceSystem\\streamlitApp\\success.wav')

                    jsonObj = {
                    "Name": name,
                    "Present": present,
                    "Class": className,
                    "DateTime": datetime.now()
                    }
                    
                    returnMsg = json.dumps(jsonObj, default=str)
                    done = True
                    print(returnMsg)
                else:
                    break
            else:
                count = count + 1

            # display the window and frame to our screen
            cv2.namedWindow("Face Recognition System", cv2.WND_PROP_FULLSCREEN)
            cv2.setWindowProperty("Face Recognition System",cv2.WND_PROP_FULLSCREEN,cv2.WINDOW_FULLSCREEN)
            cv2.imshow("Face Recognition System", frame)
            cv2.waitKey(1)
                
            # when there is no face recognized or no face in the frame or face recognized dont belong to the class
            if count == 100:
                break

            # after attendance have been recorded into database
            if done == True:
                time.sleep(5)
                break

        # close the window on the screen
        cv2.destroyAllWindows()
        break
    else:
        print("No such class exists!")
