import time, datetime, urllib, json, warnings, re, mwparserfromhell
from wikitools import *
import login #Bot password

site = wiki.Wiki() #Tell Python to use the English Wikipedia's API
site.login(login.username, login.password) #login

#routine to autoswitch some of the output - as filenames in, say, filep.unprefixedtitle have accented chars!
def pnt(s):
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode('utf-8'))

#Find pages to delete
def findpages():
    #parameters for API request
    params = {'action':'query',
              'list':'categorymembers',
              #'cmtitle':'Category:RonBotTest',
              'cmnamespace':'6',
              'cmtitle':'Category:Non-free files with orphaned versions more than 7 days old',
              'cmlimit':'500'
              }
    req = api.APIRequest(site, params) #Set the API request
    res = req.query(False) #Send the API request and store the result in res
    touse = pagelist.listFromQuery(site, res['query']['categorymembers']) #Make a list
    return touse

def versiontodelete(page):
    params = {'action':'query',
              'prop':'imageinfo',
              'titles':page.unprefixedtitle,
              'iiprop':'archivename',
              'iilimit':'max',
              'formatversion':'2',
              }
    req = api.APIRequest(site, params)
    res = req.query(False)
    whattodel = res['query']['pages'][0]['imageinfo'][1:] #Go into specifics, ignore first result (DatBot's reduced version)
    for result in whattodel:
        if 'filehidden' in result:
            print result
            try:
                del result ['filehidden'] #Remove any "filehidden" results param1
                del result ['archivename'] #Remove any "filehidden" results param2
            except:
                print "Mini error"
            whattodel = filter(None, whattodel) # Remove empty results
    return whattodel

def deletefile(page, version, token):
    params = {'action':'revisiondelete',
              'target':page.unprefixedtitle,
              'type':'oldimage',
              'hide':'content',
              'ids':version,
              'token':token,
              'reason':'Orphaned non-free file revision(s) deleted per [[WP:F5|F5]] ([[User:AmandaNP/Imagerevdel/Run|disable]])'
              }
    api.APIRequest(site, params).query() #Actually delete it  (DO NOT UNCOMMENT UNTIL BOT IS APPROVED)
    return #Stop the function, ready for the next

def abusechecks(page):
    params = {'action':'query',
              'prop':'revisions',
              'titles':page.unprefixedtitle,
              'rvlimit':'10'
              }
    req = api.APIRequest(site, params)
    res = req.query(False)
    pageid = res['query']['pages'].keys()[0]
    revisions=res['query']['pages'][pageid]['revisions']
    #print revisions
    lastuser=""
    firstrev=True
    for rev in revisions:
        if firstrev:
            firstrev=False
            continue
        timestamp = rev['timestamp']
        comment = rev['comment']
        user = rev['user']
        if 'uploaded a new version of' in comment:
            timestamp = datetime.datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')
            if timestamp < datetime.datetime.utcnow()-datetime.timedelta(days=7):
                return "Yes"
        if lastuser == user:continue
        if lastuser != user and ("bot" not in user.lower() and "bot" not in lastuser.lower()):
            return "No"
        else:
            lastuser=user
    #timestamp = res['query']['pages'][pageid]['revisions'][1]['timestamp']
    #comment = res['query']['pages'][pageid]['revisions'][1]['comment']
    

def checksize(page):
    params = {'action':'query',
              'prop':'imageinfo',
              'titles':page.unprefixedtitle,
              'formatversion':'2',
              'iiprop':'size'
              }
    req = api.APIRequest(site, params)
    res = req.query(False)
    pixel = res['query']['pages'][0]['imageinfo'][0]['width'] * res['query']['pages'][0]['imageinfo'][0]['height']
    if pixel > 105000:
    #if (res['query']['pages'][0]['imageinfo'][0]['width'] > 400) and (res['query']['pages'][0]['imageinfo'][0]['height'] > 400):
        print 'chacksize manual'
        return "Manual"
    else:
        return True

def addmanual(pagetext,file): #Just makes it a bit shorter
    pagetext = re.sub(r'[Nn]on-free reduced', 'Orphaned non-free revisions', pagetext)
    pagetext = re.sub(r'(?P<Main>\{\{(?:[Oo]rphaned non-free revisions|[Nn]on-free reduced).*?(?=}}))', r'\g<Main>|human=yes', pagetext)
    pnt("Requesting manual review on " + file)
    return pagetext

def main():
    tobreak = "no"
    pages = findpages()
    for filep in pages: #For page in the list
        if tobreak == "yes":
            break
        try: #Try to delete the old revision(s)
            if filep.unprefixedtitle == "Category:Non-free files with orphaned versions more than 7 days old needing human review": #Skip category thing
                continue
            todelete = versiontodelete(filep)
            firstversion="yes"
            for version in todelete:
                version = re.sub(r'([^!]*)!.*', r'\1', version['archivename'])
                go = startAllowed() #Check if task is enabled
                if go == "no":
                    tobreak = "yes"
                    break
                if firstversion == "yes":
                    pagepage = page.Page(site, filep.unprefixedtitle) #Hacky workaround since File and Page are different types in the module
                    pagetext = pagepage.getWikiText() 
                    #Stop if there's nobots
                    allow_bots(pagetext, "DeltaQuadBot")
                    skipcategories = page.Page(site, 'User:RonBot/1/FreeCategory').getWikiText().split("|")
                    check = abusechecks(filep) #Check if file was uploaded 2 days ago
                    if any(skipcategory in pagepage.getCategories() for skipcategory in skipcategories):
                        print "One of the potentially free categories were found. Skipping."
                        check="free"
                    if check == "No":
                        if pagetext.find('|human=yes')>0:break#Manual already set - no more to do
                        pagetext = addmanual(pagetext,filep.unprefixedtitle)
                        pagepage.edit(text=pagetext, bot=True, summary="(Image Revdel) Requesting manual review ([[User:AmandaNP/Imagerevdel/Run|disable]])") #(DO NOT UNCOMMENT UNTIL BOT IS APPROVED)
                        break #- leave for loop as we only want one entry - there may be multple versions to delete
                    if check == "free":
                        if pagetext.find('|human=yes')>0:break#Manual already set - no more to do
                        pagetext = addmanual(pagetext,filep.unprefixedtitle)
                        pagepage.edit(text=pagetext, bot=True, summary="(Image Revdel) Requesting manual review - Free file conflict ([[User:AmandaNP/Imagerevdel/Run|disable]])") #(DO NOT UNCOMMENT UNTIL BOT IS APPROVED)
                        break #- leave for loop as we only want one entry - there may be multple versions to delete
                    if  (filep) == "Manual":
                        if pagetext.find('|human=yes')>0:break#Manual already set - no more to do
                        pagetext = addmanual(pagetext,filep.unprefixedtitle)
                        pagepage.edit(text=pagetext, bot=True, summary="(Image Revdel) Requesting manual review ([[User:AmandaNP/Imagerevdel/Run|disable]])") #(DO NOT UNCOMMENT UNTIL BOT IS APPROVED)
                        break #- leave for loop as we only want one entry - there may be multple versions to delete
                #Get a token
                params = { 'action':'query', 'meta':'tokens' }
                token = api.APIRequest(site, params).query()['query']['tokens']['csrftoken']
                #Delete the revision
                deletefile(filep, version, token)
                #Remove tag
                pagetext = re.sub(r'\n*\{\{(?:[Oo]rphaned non-free revisions|[Nn]on-free reduced).*}}', '', pagetext)
                pagetext=pagetext.lstrip()
                pagepage.edit(text=pagetext, bot=True, summary="(Image Revdel) Orphaned non-free file(s) deleted per [[WP:F5|F5]] ([[User:AmandaNP/Imagerevdel/Run|disable]])") #(DO NOT UNCOMMENT UNTIL BOT IS APPROVED)
                pnt ("Revdel complete for %s" % filep.unprefixedtitle) #For debugging
                firstversion="no"
            else:
                pagepage = page.Page(site, filep.unprefixedtitle) #Hacky workaround since File and Page are different types in the module
                pagetext = pagepage.getWikiText() 
                pagetext = re.sub(r'\n*\{\{(?:[Oo]rphaned non-free revisions|[Nn]on-free reduced).*}}', '', pagetext)
                pagetext=pagetext.lstrip()
                pagepage.edit(text=pagetext, bot=True, summary="(Image Revdel) Remove banner - nothing to delete ([[User:AmandaNP/Imagerevdel/Run|disable]])") #(DO NOT UNCOMMENT UNTIL BOT IS APPROVED)

        except Exception as e: #If there's an error, ignore the file
            print e
            pass
def startAllowed():
    textpage = page.Page(site, "User:AmandaNP/Imagerevdel/Run").getWikiText()
    if textpage == "Run":
        return "run"
    else:
        return "no"

def allow_bots(pagetext, username):
    user = username.lower().strip()
    text = mwparserfromhell.parse(pagetext)
    for tl in text.filter_templates():
        if tl.name in ('bots', 'nobots'):
            break
    else:
        return True
    for param in tl.params:
        bots = [x.lower().strip() for x in param.value.split(",")]
        if param.name == 'allow':
            if ''.join(bots) == 'none': return False
            for bot in bots:
                if bot in (user, 'all'):
                    return True
        elif param.name == 'deny':
            if ''.join(bots) == 'none': return True
            for bot in bots:
                if bot in (user, 'all'):
                    return False
    return True

if __name__ == "__main__":
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        main()
