from showcaseme import app, login_manager, users, db, DEFAULT_PROFILE, DEFAULT_LISTING, TAGS, mail, listings
from showcaseme.models import User, getUserData, getListingData, userSearch, listingSearch, topSkills
from tinydb import TinyDB, Query
from flask import Flask, g, Response, redirect, url_for, request, session, abort, render_template, jsonify
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from functools import wraps
from collections import Counter
import uuid
from time import sleep
def usertype_required(f):		
    @wraps(f)		
    def decorated_function(*args, **kwargs):		
        if current_user.is_authenticated and not current_user.userType:		
            return redirect(url_for('userType', next=request.url))		
        return f(*args, **kwargs)		
    return decorated_function
@app.route('/')
def home():
	temp = []
	if current_user.is_authenticated and current_user.userType == 'student':
		stype = 'listing'
		userTags = getUserData(current_user.id)['profile']['tags']
		print(userTags)
		userArgs = {tag['name']: tag['skill'] for tag in userTags}
		print(userArgs)
		found = listingSearch(userArgs, threshold = 0.7, limit = 9)
		foundSorted = list(Counter(found).most_common())
		for listing in foundSorted:
			if not getListingData(listing[0]):
				continue
			listingData = getListingData(listing[0])
			listingData['id'] = listingData['id']
			listingData['match'] = found[listing[0]]
			listingData['name'] = listingData['title']
			temp.append(listingData)
	else:
		stype = 'student'
		for item in users.all():
			if 'profile' in item:
				item['profile']['id'] = item['id']
				temp.append(item['profile'])
	return render_template('home.html', data=temp, tags = TAGS, topSkills = topSkills(10), stype = stype)
@app.route('/student/<id>')
@app.route('/company/<id>')
def viewUser(id):
	user = getUserData(id)
	if ('profile' in user and user['userType']):
		if user['userType'] == 'student':
			return render_template('profile.html', data = user['profile'], tag = TAGS, id=id, userType = user['userType'])
		else:
			q = Query()
			return render_template('profile.html', data = user['profile'], tag = TAGS, id=id, userType = user['userType'], listings= listings.search(q.user == user['id']))
	return render_template('profile.html')

@app.route('/listing/<id>', methods=['GET', 'POST'])
def viewListing(id):
		q = Query()
		listing = listings.search(q.id == id)
		return render_template('listing.html', tag = TAGS, id = id, data=listing[0])

@usertype_required
@login_required
@app.route('/listing', methods=['GET', 'POST'])
def listing(id=False):
	q = Query()
	if request.method == 'POST' and current_user.userType=='company': #update listing
		rawListing = request.get_json()
		rawListing['user'] = current_user.id
		listing = listings.search(q.id == rawListing['id'])
		#print(len(listing) == 0)
		update = updateListing(rawListing, q)
		update.next()
		#print(update)
		#listings.update(rawListing, q.id == rawListing['id'])	
		return jsonify(result='ok')

	else: #create listing
		"""DEFAULT_LISTING['user'] = current_user.id
		return render_template('listing.html', tag = TAGS, id = uuid.uuid4(), data=DEFAULT_LISTING)"""
		listingId = str(uuid.uuid4())
		url = addListing(listingId)
		url.next()
		#print("oogah")
		return url.next()

def addListing(listingId, user=None):
	rawListing=DEFAULT_LISTING
	rawListing['id'] =  listingId
	if not user:
		rawListing['user'] = current_user.id
	else:
		rawListing['user'] = user
	listing = listings.all()
	yield listings.insert(rawListing)
	yield redirect("/listing/"+listingId)

def updateListing(rawListing, q):
	yield listings.update(rawListing, q.id == rawListing['id'])	

@app.route('/about')
@usertype_required
def about():
	return render_template('about.html')

@app.route('/usertype', methods=["GET", "POST"])
def userType():
	if request.method == "POST": #The user is setting their datatype
		u = Query()
		users.update({'userType': request.get_json()['userType']}, u.id == current_user.id)
		user = User(current_user.id)
		login_user(user)
		return jsonify(result = 'ok')
	else: #Their usertype has not been set
		return render_template('userType.html')
@app.route("/signup", methods=["GET"])
def signup():
	return render_template('signup.html')
@app.route("/login", methods=["GET", "POST"])
def login(): 
	if request.method == 'POST':
		uid = request.get_json()['uid']
		if getUserData(uid): #Means that they have an account
			user = User(uid)
			login_user(user)
			if current_user.is_authenticated and not current_user.userType:	
				return jsonify(result='bad')
			else:
				return jsonify(result='ok')
		else: #Means that this is their first time with us
				users.insert({'name': request.get_json()['name'], 'id': uid})
				user = User(uid)
				login_user(user)
				if current_user.is_authenticated and not current_user.userType:	
					return jsonify(result='bad')	
				else:
					return jsonify(result='ok')
	else: #The login page for the form
		return render_template('login.html')

@app.route("/logout")
@login_required
def logout():
	logout_user()
	return redirect("/")
@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
	if request.method == 'POST':
		profile = request.get_json()
		person = Query()
		users.update({'profile': profile}, person.id == current_user.id)
		return jsonify(result='ok')
	else:
		user = getUserData(current_user.id)
		if current_user.userType == 'student':
			if 'profile' in user:
				return render_template('profile.html', data = user['profile'], tag = TAGS, id=current_user.id, userType = current_user.userType)
			else:
				DEFAULT_PROFILE['name'] = current_user.name
				return render_template('profile.html', data = DEFAULT_PROFILE, tag = TAGS, id=current_user.id, userType = current_user.userType)
		else: #they are a company
			q = Query()
			listing = listings.search(q.user == current_user.id)
			if 'profile' in user:
				return render_template('profile.html', data = user['profile'], tag = TAGS, id=current_user.id, listings = listing, userType = current_user.userType )
			else:
				DEFAULT_PROFILE['name'] = current_user.name
				return render_template('profile.html', data = DEFAULT_PROFILE, tag = TAGS, id=current_user.id, listings = listing, userType = current_user.userType)

@app.route("/search", methods=["GET"])
def search():
	found = userSearch(request.args)
	foundSorted = list(Counter(found).most_common())
	#print(request.args)
	#print([getUserData(user)['profile'] for user in sorted(found, key=found.get, reverse=True) if 'profile' in getUserData(user)])
	return render_template('search.html', data = [dict(getUserData(user[0])['profile'].items() +
		{'id': getUserData(user[0])['id']}.items() + 
		{'match': found[user[0]]}.items()) for user in foundSorted if (getUserData(user[0]) and 'profile' in getUserData(user[0]))], 
		tags = TAGS,
		stype = 'student')

@app.route("/searchlistings", methods=["GET"])
def searchListings():
	print(request.args)
	found = listingSearch(request.args)
	foundSorted = list(Counter(found).most_common())
	listings = []
	for listing in foundSorted:
		if not getListingData(listing[0]):
			continue
		listingData = getListingData(listing[0])
		listingData['id'] = listingData['id']
		listingData['match'] = found[listing[0]]
		listingData['name'] = listingData['title']
		listings.append(listingData)
	return render_template('search.html',
		data = listings,
		tags = TAGS,
		stype = 'listing')

@app.route('/send-mail/', methods=['GET', 'POST'])
def send_mail():
	if request.method == 'POST': #Sending the message
		msg = request.get_json()
		mail.send_message(
			msg['subject'],
			sender=(current_user.name, "ARHAM FIREBASE EMAIL THINGY"),
			recipients=[getUserData(msg['target'])['profile']['name'], "ARHAM MORE EMAILS"],
			body=msg['body']
		)
		return jsonify(result='ok')
	return jsonify(result='ok')
# handle login failed
@app.errorhandler(401)
def page_not_found(e):
	return Response('<p>Login failed</p>')  
# callback to reload the user object        
@login_manager.user_loader
def load_user(userid):
	if getUserData(userid):
		return User(userid)