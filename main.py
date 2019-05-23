from wikitools import *
import time
import datetime
import urllib
import json
import login #Bot password
import warnings
import re
import mwparserfromhell
import datetime

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
              'cmtitle':'Category:Non-free files with orphaned versions more than 7 days old',
              'cmlimit':'max'
              }
    print "findpages.params"
    req = api.APIRequest(site, params) #Set the API request
    print "findpages.req"
    res = req.query(False) #Send the API request and store the result in res
    print "findpages.res",res
    touse = pagelist.listFromQuery(site, res['query']['categorymembers']) #Make a list
    print "findpages.touse"
    return touse

def versiontodelete(page):
    params = {'action':'query',
              'prop':'imageinfo',
              'titles':page.unprefixedtitle,
              'iiprop':'archivename',
              'iilimit':'max',
              'formatversion':'2',
              }
    print "versiontodelete.params"
    req = api.APIRequest(site, params)
    print "versiontodelete.req"
    res = req.query(False)
    print "versiontodelete.res"
    whattodel = res['query']['pages'][0]['imageinfo'][1:] #Go into specifics, ignore first result (DatBot's reduced version)
    print "versiontodelete.whattodel", whattodel
    for result in whattodel:
         print "versiontodelete.for loop", result
         if 'filehidden' in result:
             print "versiontodelete.for loop delete", result
             del result ['filehidden'] #Remove any "filehidden" results param1
             del result ['archivename'] #Remove any "filehidden" results param2
             whattodel = filter(None, whattodel) # Remove empty results
             print "versiontodelete.whattodel2", whattodel
    return whattodel

def deletefile(page, version, token):
    params = {'action':'revisiondelete',
              'target':page.unprefixedtitle,
              'type':'oldimage',
              'hide':'content',
              'ids':version,
              'token':token,
              'reason':'Orphaned non-free file revision(s) deleted per [[WP:F5|F5]] ([[User:DeltaQuad/Imagerevdel/Run|disable]])'
              }
    print "deletefile.params"
    print "page.unprefixedtitle"#,page.unprefixedtitle
    print "version", version
    print "token", token
    api.APIRequest(site, params).query() #Actually delete it  (DO NOT UNCOMMENT UNTIL BOT IS APPROVED)
    print "deletefile.finish"
    return #Stop the function, ready for the next

def abusechecks(page):
    params = {'action':'query',
              'prop':'revisions',
              'titles':page.unprefixedtitle,
              'rvlimit':'10'
              }
    print "abusechecks.params"
    req = api.APIRequest(site, params)
    print "abusechecks.req"
    res = req.query(False)
    print "abusechecks.res"
    pageid = res['query']['pages'].keys()[0]
    print "abusechecks.pageid"
    timestamp = res['query']['pages'][pageid]['revisions'][1]['timestamp']
    print "abusechecks.timestamp"
    comment = res['query']['pages'][pageid]['revisions'][1]['comment']
    print "abusechecks.comment"
    pnt(comment)
    if 'uploaded a new version of' in comment:
        print "abusechecks.if"
        timestamp = datetime.datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%SZ')
        print "abusechecks.timestamp2", "*";datetime.datetime.utcnow();"*", "*";timestamp;"*"
        print 
        if timestamp < datetime.datetime.utcnow()-datetime.timedelta(days=7):
            print 'abusereturn yes'
            return "Yes"
        else:
            print 'abusereturn no 1'
            print timestamp
            print datetime.datetime.utcnow()
            print datetime.datetime.utcnow()-datetime.timedelta(days=7)
            return "No"
    else:
        print 'abusereturn no 2'
        return "No"

def checksize(page):
    params = {'action':'query',
              'prop':'imageinfo',
              'titles':page.unprefixedtitle,
              'formatversion':'2',
              'iiprop':'size'
              }
    print "checksize.params"
    req = api.APIRequest(site, params)
    print "checksize.req"
    res = req.query(False)
    print "checksize.res"
    print res
    print "width = ",res['query']['pages'][0]['imageinfo'][0]['width']
    print "height = ",res['query']['pages'][0]['imageinfo'][0]['height']
    pixel = res['query']['pages'][0]['imageinfo'][0]['width'] * res['query']['pages'][0]['imageinfo'][0]['height']
    print pixel
    if pixel > 105000:
    #if (res['query']['pages'][0]['imageinfo'][0]['width'] > 400) and (res['query']['pages'][0]['imageinfo'][0]['height'] > 400):
        print 'chacksize manual'
        return "Manual"
    else:
        return True

def addmanual(pagetext): #Just makes it a bit shorter
    print "addmanual"
    pnt (pagetext)
    print "SUB1"
    pagetext = re.sub(r'[Nn]on-free reduced', 'Orphaned non-free revisions', pagetext)
    pnt (pagetext)
    print "SUB2"
    pagetext = re.sub(r'(?P<Main>\{\{(?:[Oo]rphaned non-free revisions|[Nn]on-free reduced).*?(?=}}))', r'\g<Main>|human=yes', pagetext)
    pnt (pagetext)
    print "SUBEND"
    return pagetext

def main():
    tobreak = "no"
    pages = findpages()
    print "main.pages"
    for filep in pages: #For page in the list
        print "main.for filp"
        #print(filep.unprefixedtitle)
        if tobreak == "yes":
            break
        try: #Try to delete the old revision(s)
            if filep.unprefixedtitle == "Category:Non-free files with orphaned versions more than 7 days old needing human review": #Skip category thing
                continue
            todelete = versiontodelete(filep)
            print "main.todelete"
            firstversion="yes"
            print todelete
            for version in todelete:
                print version
                version = re.sub(r'([^!]*)!.*', r'\1', version['archivename'])
                print version
                print "main.for version"
                go = startAllowed() #Check if task is enabled
                if go == "no":
                    tobreak = "yes"
                    print tobreak
                    break
                if firstversion == "yes":
                    pagepage = page.Page(site, filep.unprefixedtitle) #Hacky workaround since File and Page are different types in the module
                    print "main.pagepage"
                    pagetext = pagepage.getWikiText() 
                    #Stop if there's nobots
                    allow_bots(pagetext, "RonBot")
                    print "main.allowbots"
                    skipcategories = page.Page(site, 'User:RonBot/1/FreeCategory').getWikiText().split("|")
                    check = abusechecks(filep) #Check if file was uploaded 2 days ago 
                    if any(skipcategory in pagepage.getCategories() for skipcategory in skipcategories):
                        print "One of the potentially free categories were found. Skipping."
                        check="No"
                    print "main.check",check
                    print pagetext.find('|human=yes')
                    if pagetext.find('|human=yes')>0:
                        print 'Manual already set - no more to do'
                        break
                    if check == "No":
                        print 'handle check=no'
                        pagetext = addmanual(pagetext)
                        print "main.no.pagetext", pagetext
                        pagepage.edit(text=pagetext, bot=True, summary="(Image Revdel) Requesting manual review ([[User:DeltaQuad/Imagerevdel/Run|disable]])") #(DO NOT UNCOMMENT UNTIL BOT IS APPROVED)
                        break #- leave for loop as we only want one entry - there may be multple versions to delete
                    if checksize(filep) == "Manual":
                        print 'handle checksize manual'
                        pagetext = addmanual(pagetext)
                        print "main.manual.pagetext", pagetext
                        pagepage.edit(text=pagetext, bot=True, summary="(Image Revdel) Requesting manual review ([[User:DeltaQuad/Imagerevdel/Run|disable]])") #(DO NOT UNCOMMENT UNTIL BOT IS APPROVED)
                        break #- leave for loop as we only want one entry - there may be multple versions to delete
                #Get a token
                params = { 'action':'query', 'meta':'tokens' }
                print "main.params"
                token = api.APIRequest(site, params).query()['query']['tokens']['csrftoken']
                print "main.token", token
                #Delete the revision
                deletefile(filep, version, token)
                print "main.deletefile"
                #Remove tag
                pagetext = re.sub(r'\n*\{\{(?:[Oo]rphaned non-free revisions|[Nn]on-free reduced).*}}', '', pagetext)
                pagetext=pagetext.lstrip()
                print "main.pagetext"
                pagepage.edit(text=pagetext, bot=True, summary="(Image Revdel) Orphaned non-free file(s) deleted per [[WP:F5|F5]] ([[User:DeltaQuad/Imagerevdel/Run|disable]])") #(DO NOT UNCOMMENT UNTIL BOT IS APPROVED)
                pnt ("Done for %s" % filep.unprefixedtitle) #For debugging
                print
                firstversion="no"
            else:
                pagepage = page.Page(site, filep.unprefixedtitle) #Hacky workaround since File and Page are different types in the module
                print "main.pagepage"
                pagetext = pagepage.getWikiText() 
                pagetext = re.sub(r'\n*\{\{(?:[Oo]rphaned non-free revisions|[Nn]on-free reduced).*}}', '', pagetext)
                pagetext=pagetext.lstrip()
                print "main.pagetext"
                pagepage.edit(text=pagetext, bot=True, summary="(Image Revdel) Remove banner - nothing to delete ([[User:DeltaQuad/Imagerevdel/Run|disable]])") #(DO NOT UNCOMMENT UNTIL BOT IS APPROVED)

        except Exception as e: #If there's an error, ignore the file
            print e
            pass
def startAllowed():
    textpage = page.Page(site, "User:DeltaQuad/Imagerevdel/Run").getWikiText()
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