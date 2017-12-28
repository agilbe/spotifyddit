import os
if os.environ['SERVER_SOFTWARE'].startswith('Development'): #dev_appserver
    from secrets import CLIENT_ID, CLIENT_SECRET
    RED_URI = 'http://localhost:8080/'
else:
    from secretsd import CLIENT_ID, CLIENT_SECRET
    RED_URI = 'https://spotifyddit.appspot.com/'
    
GRANT_TYPE = 'authorization_code'
APP_NAME = "spotifyddit"
NUM_CHARS = 45 #for playlist name length


import webapp2, urllib2, urllib, json, jinja2, logging, sys, time
import base64, Cookie, hashlib, hmac, email
from google.appengine.ext import db
from google.appengine.api import urlfetch
from random import randint
sys.path.insert(0, 'libs')
from BeautifulSoup import BeautifulSoup, SoupStrainer

JINJA_ENVIRONMENT = jinja2.Environment(loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


### this is our user database model. We will use it to store the access_token
class User(db.Model):
    uid = db.StringProperty(required=True)
    displayname = db.StringProperty(required=False)
    img = db.StringProperty(required=False)   
    access_token = db.StringProperty(required=True)
    refresh_token = db.StringProperty(required=False)
    profile_url=db.StringProperty(required=False)
    api_url=db.StringProperty(required=False) 


class Artist:
    def __init__(self, artistdict):
        self.genres = []
        if 'genres' in artistdict:
            self.genres = artistdict['genres']
        else:
            self.genres = []
        self.href = artistdict['href']
        self.id = artistdict['id']
        self.images = []
        if 'images' in artistdict:
            self.images = artistdict['images']
        else:
            self.images = []
        self.name = artistdict['name']
        self.uri = artistdict['uri']
        self.external_urls = artistdict['external_urls']
    
    def toJSON(self):
        return json.dumps(self.__dict__)

class Album:
    def __init__(self, albumdict):
        self.href = albumdict['href']
        self.id = albumdict['id']
        self.images = albumdict['images']
        self.name = albumdict['name']
        self.uri = albumdict['uri']
        self.external_urls = albumdict['external_urls']

    def toJSON(self):
        return json.dumps(self.__dict__)

class Playlist:
    def __init__(self, playlistdict):
        self.href = playlistdict['href']
        self.id = playlistdict['id']
        if 'images' in playlistdict:
            self.images = playlistdict['images']
        else:
            self.images = []
        self.name = playlistdict['name']
        self.owner = playlistdict['owner']
        self.collaborative = playlistdict['collaborative']
        self.public = playlistdict['public']
        if 'tracks' in playlistdict:
            self.tracks = playlistdict['tracks']
        else:
            self.tracks = []
        self.uri = playlistdict['uri']
        self.external_urls = playlistdict['external_urls']

    def toJSON(self):
        return json.dumps(self.__dict__)

class Song:
    def __init__(self, trackdict):
        self.album = Album(trackdict['album'])
        #self.artists = trackdict['artists']
        self.artists = [Artist(item) for item in trackdict['artists']]
        self.href = trackdict['href']
        self.id = trackdict['id']
        self.name = trackdict['name']
        self.preview_url = trackdict['preview_url']
        self.uri = trackdict['uri']
        self.external_urls = trackdict['external_urls']
        
    def toJSON(self):
        return json.dumps(self.__dict__)

### helper functions 

def safeGet(url): #python2
    try:
        req = urllib2.Request(url, None)
        return urllib2.urlopen(req)
    except urllib2.URLError, e:
        if hasattr(e,"code"):
            print "The server couldn't fulfill the request."
            print "Error code: ", e.code
        elif hasattr(e,'reason'):
            print "We failed to reach a server"
            print "Reason: ", e.reason
        return None

def set_cookie(response, name, value, domain=None, path="/", expires=None):
    """Generates and signs a cookie for the give name/value"""
    timestamp = str(int(time.time()))
    value = base64.b64encode(value)
    signature = cookie_signature(value, timestamp)
    cookie = Cookie.BaseCookie()
    cookie[name] = "|".join([value, timestamp, signature])
    cookie[name]["path"] = path
    if domain: cookie[name]["domain"] = domain
    if expires:
        cookie[name]["expires"] = email.utils.formatdate(
            expires, localtime=False, usegmt=True)
    response.headers.add("Set-Cookie", cookie.output()[12:])
    logging.info("SETTING COOKIE" + name)


def parse_cookie(value):
    """Parses and verifies a cookie value from set_cookie"""
    if not value: return None
    parts = value.split("|")
    if len(parts) != 3: return None
    if cookie_signature(parts[0], parts[1]) != parts[2]:
        logging.warning("Invalid cookie signature %r", value)
        return None
    timestamp = int(parts[1])
    if timestamp < time.time() - 30 * 86400:
        logging.warning("Expired cookie %r", value)
        return None
    try:
        return base64.b64decode(parts[0]).strip()
    except:
        return None

def cookie_signature(*parts):
    """
    Generates a cookie signature.

    We use the Spotify app secret since it is different for every app (so
    people using this example don't accidentally all use the same secret).
    """
    chash = hmac.new(CLIENT_SECRET, digestmod=hashlib.sha1)
    for part in parts: chash.update(part)
    return chash.hexdigest()
    
    
def spotifyurlfetch(url,access_token,params=None, method=urlfetch.GET):
    headers = {'Authorization': 'Bearer '+access_token}
    response = urlfetch.fetch(url,method=method, payload=params, headers=headers)
    return response.content

### handlers

class BaseHandler(webapp2.RequestHandler):
    # @property followed by def current_user makes so that if x is an instance
    # of BaseHandler, x.current_user can be referred to, which has the effect of
    # invoking x.current_user()
    @property
    def current_user(self):
        """Returns the logged in Spotify user, or None if unconnected."""
        logging.info("GETTING CURRENT USER")
        if not hasattr(self, "_current_user"):
            self._current_user = None
            # find the user_id in a cookie
            user_id = parse_cookie(self.request.cookies.get("spotify_user"))
            logging.info(user_id) #is None
            if user_id:
                self._current_user = User.get_by_key_name(user_id)
        return self._current_user

class HomeHandler(BaseHandler):
    def get(self):
        template = JINJA_ENVIRONMENT.get_template('index.html')
        
        # check if they are logged in
        user = self.current_user
        tvals = {'current_user':user, 'app_name': APP_NAME}
        if user != None:
            
            # IF I NEED PLAYLISTS
            # url = "https://api.spotify.com/v1/users/%s/playlists?limit=25"%user.uid
            ## in the future, should make this more robust so it checks if the access_token
            ## is still valid and retrieves a new one using refresh_token if not
            # response = json.loads(spotifyurlfetch(url,user.access_token))
            # if "items" in response:
            #     tvals["playlists"]=[Playlist(item) for item in response["items"]]
            #     logging.info(len(tvals["playlists"]))
            #     #grab reddit data
            
            testurls = ['https://www.reddit.com/r/EDM/comments/7i22of/show_me_the_best_three_songs_you_know/', 'https://www.reddit.com/r/EDM/comments/6v84qy/best_songs_by_the_best_artists/']

            tvals["error"] = None
            if self.request.get('ex'):
                redditurl = testurls[randint(1, len(testurls)) - 1]
            else:
                redditurl = self.request.get('redditinput')
            if redditurl: #add some sort of checking for url
                #if url not valid add tvals["error"] = 'url'?
                try: 
                    htmlstring = safeGet(redditurl)
                    if htmlstring is not None:
                        htmlstring = htmlstring.read()
                        soup = BeautifulSoup(htmlstring)
                        articlename = soup.find("a", {"class" : "title may-blank "}).text
                        srname = "reddit"
                        srlink = "-created with " + APP_NAME + "- "
                        if '/r/' in redditurl:
                            srname = "r/" + redditurl.split('/r/')[1].split('/')[0] #haha
                        for attr, item in soup.find("input", {"id" : "shortlink-text"}).attrs:
                            if attr == 'value':
                                srlink += item
                        tvals["srname"] = srname
                        tvals["srlink"] = srlink
                        tvals["articlename"] = articlename
                        try:
                            songlist = [item['href'].encode('utf-8') for item in soup.findAll('a', href=True) if 'open.spotify.com/track' in item['href']]
                            #get song id from url and populate list of song instances
                            newsonglist = [Song(json.loads(spotifyurlfetch('https://api.spotify.com/v1/tracks/' + track.split('?')[0].split('/')[-1], user.access_token))) for track in songlist]
                            if len (newsonglist):
                                tvals["results"] = newsonglist
                        except:
                            tvals["results"] = None
                            tvals["error"] = "loggedout"
                    else: 
                        logging.info("error scraping reddit")
                        tvals["results"] = None
                        tvals["error"] = "reddit"
                        tvals["tryagain"] = redditurl
                except:
                    logging.info("reddit could be down or could be an error in my code, who knows?")
                    tvals["results"] = None
                    tvals["error"] = "redditservers"
                    tvals["tryagain"] = redditurl
            else: #if no url or improperly formatted
                logging.info("error in URL")
                tvals["results"] = None
                #tvals["error"] = "url"
        else:
            logging.info("NO USER")
            tvals['error'] = 'inactivity'
            set_cookie(self.response, "spotify_user", "", expires=time.time() - 86400)
            
            #self.redirect("/") #oops if the user isn't logged in this just redirects to "/" infinitely
            #log out user here?
            
            logging.info("error with logging in - fix this")
        
        self.response.write(template.render(tvals)) 

class LoginHandler(BaseHandler):
    def get(self):
        # after login; redirected here      
        # did we get a successful login back?
        args = {}
        args['client_id']= CLIENT_ID
        from google.appengine.api import app_identity
        server_url = app_identity
        logging.info("@@@@@@@@@@@@@@@@")
        logging.info(server_url)
        verification_code = self.request.get("code")
        logging.info(self.request)
        if '?code=' in self.request.referrer:
            verification_code = self.request.referrer.split('?code=')[1]
        if verification_code:
            # if so, we will use code to get the access_token from Spotify
            # This corresponds to STEP 4 in https://developer.spotify.com/web-api/authorization-guide/
                
            args["client_secret"] = CLIENT_SECRET
            args["grant_type"] = GRANT_TYPE
            args["code"] = verification_code                # the code we got back from Spotify
            args['redirect_uri']=RED_URI
            
            # We need to make a post request, according to the documentation 
            
            #headers = {'content-type': 'application/x-www-form-urlencoded'}
            url = "https://accounts.spotify.com/api/token"
            response = urlfetch.fetch(url, method=urlfetch.POST, payload=urllib.urlencode(args))
            response_dict = json.loads(response.content)
            logging.info(response_dict["access_token"])
            access_token = response_dict["access_token"]
            refresh_token = response_dict["refresh_token"]

            # Download the user profile. Save profile and access_token
            # in Datastore; we'll need the access_token later
            
            ## the user profile is at https://api.spotify.com/v1/me
            profile = json.loads(spotifyurlfetch('https://api.spotify.com/v1/me',access_token))
            logging.info(profile)
           
            user = User(key_name=str(profile["id"]), uid=str(profile["id"]),
                        displayname=str(profile["display_name"]), access_token=access_token,
                        profile_url=profile["external_urls"]["spotify"], api_url=profile["href"], refresh_token=refresh_token)
            if profile.get('images') is not None:
                user.img = profile["images"][0]["url"]
            user.put()
            
            ## set a cookie so we can find the user later
            set_cookie(self.response, "spotify_user", str(user.uid), expires=time.time() + 30 * 86400)
            
            ## okay, all done, send them back to the App's home page
            self.redirect("/")

        else:
            # not logged in yet-- send the user to Spotify to do that
            # This corresponds to STEP 1 in https://developer.spotify.com/web-api/authorization-guide/
            
            args['redirect_uri']=RED_URI
            args['response_type']="code"
            #ask for the necessary permissions - see details at https://developer.spotify.com/web-api/using-scopes/
            args['scope']="user-library-modify playlist-modify-private playlist-modify-public playlist-read-collaborative"
            
            url = "https://accounts.spotify.com/authorize?" + urllib.urlencode(args)
            logging.info(url)
            self.redirect(url)


class LogoutHandler(BaseHandler):
    def get(self):
        set_cookie(self.response, "spotify_user", "", expires=time.time() - 86400)
        self.redirect("/")

'''
idea: when rendering the songs to the index.html template, render them
directly into a form with radio buttons that the user can then select
and add to playlist DONE

TODO: figure out what i need to grab from each song instance to add it to a playlist
and send that to the template in HomeHandler NVM i can just send the entire song obj
'''
class PlaylistHandler(BaseHandler):
    def post(self):
        template = JINJA_ENVIRONMENT.get_template('response.html')
        user = self.current_user
        articlename = self.request.params.get('articlename')
        srname = self.request.params.get('srname')
        if len(articlename) > NUM_CHARS:
            articlename = articlename[:NUM_CHARS] + "..."
        srlink = self.request.params.get('srlink')
        tvals = {'current_user':user, 'app_name':APP_NAME, 'articlename':articlename, 'srname':srname}
        songlist = self.request.params.getall('song') # a list of the song uris

        addplaylisturl = "https://api.spotify.com/v1/users/%s/playlists"%user.uid
        params = json.dumps({"name": srname + ": " + articlename, "description": srlink})
        responsep = Playlist(json.loads(spotifyurlfetch(addplaylisturl,user.access_token, params=params, method=urlfetch.POST)))
        tvals['playlist'] = responsep
        playlistid = responsep.id
        params = json.dumps({'uris':songlist})
        addtracksurl = "https://api.spotify.com/v1/users/%s/playlists/%s/tracks"%(user.uid, playlistid)
        responsetracks = json.loads(spotifyurlfetch(addtracksurl, user.access_token, params=params, method=urlfetch.POST))   
        #has snapshot_id of playlist     
        logging.info(responsetracks)
        
        self.response.write(template.render(tvals)) 


application = webapp2.WSGIApplication([\
    ("/", HomeHandler),
    ("/createplaylist", PlaylistHandler),
    ("/auth/login", LoginHandler),
    ("/auth/logout", LogoutHandler)
], debug=True)