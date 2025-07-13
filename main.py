# pip install pymysql or mysqlclient
# pip install flask-sqlalchemy
# pip install flask-mail


from flask import Flask,render_template,request,jsonify,session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import Mapped, mapped_column
from werkzeug.utils import secure_filename
from sqlalchemy import DateTime
from datetime import datetime
import json,os
from flask_mail import Mail
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import google.auth.transport.requests
from googleapiclient.http import MediaFileUpload   # ← add this
from flask import redirect



with open('config.json',"r") as c:
    params=json.load(c)["params"]
local_server=True
userid=""
app=Flask(__name__)
SCOPES = ['https://www.googleapis.com/auth/drive.file']
app.config['UPLOAD_FOLDER']=params['upload_location']
app.secret_key = 'my_ssecret_key'
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT='465',
    MAIL_USE_SSL=True,
    MAIL_USERNAME=params['user'],
    MAIL_PASSWORD=params['password']   
)
mail=Mail(app)
if local_server:
    app.config["SQLALCHEMY_DATABASE_URI"]=params['local_uri']
else:
    app.config["SQLALCHEMY_DATABASE_URI"]=params['prod_uri']



db = SQLAlchemy(app)




class Contacts(db.Model):
    serial_no: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    email_address: Mapped[str] = mapped_column(nullable=False)
    phone_number: Mapped[str] = mapped_column(nullable=False)
    message: Mapped[str] = mapped_column(nullable=False) 
    created_on: Mapped[datetime] = mapped_column(DateTime, nullable=True)

class Posts(db.Model):
    sno: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(nullable=False)
    content: Mapped[str] = mapped_column(nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    slug: Mapped[str] = mapped_column(nullable=False) 
    tag_line: Mapped[str] = mapped_column(nullable=False) 
    bg_image: Mapped[str] = mapped_column(nullable=True) 
  
class Valid_users(db.Model):
    user_id:Mapped[str]=mapped_column(nullable=False,primary_key=True)
    password:Mapped[str]=mapped_column(nullable=False)
    is_admin:Mapped[str]=mapped_column(nullable=False)



@app.route("/home",methods=['GET'])
def home():
    total_posts=Posts.query.count()
    # per_page=params['no_of_posts']
    current_page=request.args.get('current_page',1,type=int)
    per_page=request.args.get('pagesize',1,type=int)
    # posts=Posts.query.all()[0:params['no_of_posts']]
    # return render_template('home.html',params=params,content=posts)
    posts=Posts.query.offset((current_page-1)*per_page).limit(per_page).all()
    total_pages=(total_posts +per_page-1)//per_page

    return render_template('home.html',params=params,content=posts,current_page=current_page,total_pages=total_pages,pagesize=per_page)




@app.route("/about")
def about():
    return render_template('about.html',params=params)

@app.route("/sample_post/<string:urlslug>")
def post(urlslug):
    print(urlslug)
    posts=Posts.query.filter(Posts.slug==urlslug).first()
    print(posts.title,posts.bg_image)
    return render_template('post.html',params=params,posts=posts)

@app.route("/contact",methods=['POST','GET'])
def contact():
    if request.method=='POST':
        mname=request.form.get('name')
        memail=request.form.get('email')
        mphone=request.form.get('phone_no')
        if mphone and len(mphone) == 10 and mphone.isdigit():
            print("Valid phone number")
        else:
         print("Invalid phone number: must be exactly 10 digits")
         return jsonify({"Error":"phone number should have exactly 10 digits in it"}),400
        mmsg=request.form.get('msg')
        entry=Contacts(name=mname,phone_number=mphone,email_address=memail,message=mmsg,created_on=datetime.now())
        db.session.add(entry)
        db.session.commit()
        mail.send_message("new message from   "+ mname,sender=memail,recipients=[params['user'],'girish_karhadkar@yahoo.in'],
                            body="there is a new record inserted in contacts with "+mmsg+"\n"+mphone
                          )
        return jsonify({"Message":"Successfully created the record"}),201
    else:
        return render_template('contact.html',params=params)
    
@app.route("/",methods=['GET','POST'])
def searchuser():
    userid=""
    if 'user' in session and session['user']==userid:
         posts=Posts.query.all()[0:params['no_of_posts']]
         return render_template('home.html',params=params,content=posts)

    if request.method=='GET':
        return render_template('index.html',params=params)
    elif request.method=='POST':
        user_id=request.form.get('user_id')
        password=request.form.get('password')
        print("i am here","user_id=",user_id,"password=",password)
        if user_id is None or user_id.strip()=="" or password is None or password.strip()=="":
         return jsonify({"Error":"user id and password both should be provided"})
        users=Valid_users.query.filter(Valid_users.user_id==user_id,Valid_users.password==password).first()
        if users is None:
            return jsonify({"Error":"Invalid user Id"}),404
        else:
            
            print("i am about to render the home page")
            session['user']=user_id
            userid=userid
            if users.is_admin=="Y":
                posts=Posts.query.all()[0:params['no_of_posts']]
                return render_template('dashboard.html',params=params,content=posts)
            else:
                posts=Posts.query.all()[0:params['no_of_posts']]
                return render_template('home.html',params=params,content=posts)


@app.route('/dashboard',methods=['GET'])
def showdashboard():
    posts=Posts.query.all()[0:params['no_of_posts']]
    return render_template('dashboard.html',params=params,content=posts)



@app.route('/uploader',methods=['GET','POST'])
def uploader():
    if 'user' in session and session['user']==session.get('user'):
        if request.method=='POST':
            f=request.files['file1']
            if f.filename == '':
                return 'No file selected'
            f.save(os.path.join(app.config['UPLOAD_FOLDER'],secure_filename(f.filename)))
            return "Uploaded Successfully"
    else:
        return "Unauthorized", 403
    
        
@app.route('/logout')
def logout():
    session.pop('user')
    return redirect('/')





@app.route('/edit/<int:sno>',methods=['POST','GET'])
def updatepost(sno):
    if request.method=="GET":
        post=Posts.query.filter(Posts.sno==sno).first()
        return render_template("edit.html",params=params,content=post)
    if request.method=="POST":
        ltitle=request.form.get('title')
        lcontent=request.form.get('content')
        lslug=request.form.get('slug')
        ltagline=request.form.get('tag_line')
        limage=request.form.get('image')
        print("limage=",limage)
        if sno==0:
            print("i am inside if condition sno=00")
            entry=Posts(title=ltitle,content=lcontent,slug=lslug,tag_line=ltagline,bg_image=limage,date=datetime.now())
            db.session.add(entry)
            db.session.commit()
            posts=Posts.query.all()[0:params['no_of_posts']]
            return render_template('dashboard.html',params=params,content=posts)
        else:
            existing_record=Posts.query.filter(Posts.sno==sno).first()
            existing_record.title=ltitle
            existing_record.content=lcontent
            existing_record.slug=lslug
            existing_record.tag_line=ltagline
            existing_record.bg_image=limage
            existing_record.date=datetime.now()
            db.session.commit()
        posts=Posts.query.all()[0:params['no_of_posts']]
        return render_template('dashboard.html',params=params,content=posts)




@app.route('/delete/<string:slug>',methods=['GET'])
def deletepost(slug):
    remove=Posts.query.filter(Posts.slug==slug).first()
    print("I am inside delete")
    if remove:
        db.session.delete(remove)
        db.session.commit()
        rem_posts=Posts.query.all()[0:params['no_of_posts']]
        return render_template('dashboard.html',params=params,content=rem_posts)
    else:
        return jsonify({"Error":"Not found"}),404

app.run(debug=True)
