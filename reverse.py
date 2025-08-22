import time, datetime, urllib, json, warnings, re, mwparserfromhell
import mwclient
import login  # Bot password

site = mwclient.Site('en.wikipedia.org', path='/w/')
site.login(login.username, login.password)

DEBUG = True  # Set to False to silence debug output

# routine to autoswitch some of the output - as filenames in, say, filep.page_title have accented chars!
def pnt(s):
    if not DEBUG:
        return
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode('utf-8'))

#Find pages to delete
def findpages():
    #parameters for API request
    params = {
        'action': 'query',
        'list': 'categorymembers',
        #'cmtitle':'Category:RonBotTest',
        'cmnamespace': '6',
        'cmtitle': 'Category:Non-free files with orphaned versions more than 7 days old',
        'cmdir': 'desc',
        'cmlimit': '500'
    }
    res = site.api(**params)  # Send the API request and store the result
    touse = [site.pages[page['title']] for page in res['query']['categorymembers']]
    pnt(f"findpages: found {len(touse)} pages to process")
    return touse

def versiontodelete(page):
    params = {
        'action': 'query',
        'prop': 'imageinfo',
        'titles': page.name,
        # Include timestamp so we can supply it to revisiondelete later
        'iiprop': 'archivename|timestamp',
        'iilimit': 'max',
        'formatversion': '2',
    }
    pnt(f"versiontodelete: fetching revisions for {page.page_title}")
    res = site.api(**params)
    whattodel = res['query']['pages'][0]['imageinfo'][1:] #Go into specifics, ignore first result (DatBot's reduced version)
    for result in whattodel:
         if 'filehidden' in result:
            try:
                del result['filehidden']  # Remove any "filehidden" results param1
                del result['archivename']  # Remove any "filehidden" results param2
            except:
                pnt("Mini error")
            whattodel = list(filter(None, whattodel))  # Remove empty results
    pnt(f"versiontodelete: {len(whattodel)} revisions to check")
    return whattodel

def deletefile(page, archivename, token):
    # revisiondelete for file revisions requires the timestamp as the id
    timestamp = archivename.split('!')[0]
    params = {
        'target': page.name,
        'type': 'oldimage',
        'hide': 'content',
        'ids': timestamp,
        'token': token,
        'reason': 'Orphaned non-free file revision(s) deleted per [[WP:F5|F5]] ([[User:AmandaNP/Imagerevdel/Run|disable]])',
    }
    pnt(f"deletefile: deleting {page.page_title} revision {timestamp}")
    print(json.dumps(params, indent=2, ensure_ascii=False))
    site.post('revisiondelete', **params)  # Actually delete it (disabled until approval)
    return  # Stop the function, ready for the next

def abusechecks(page):
    params = {'action':'query',
              'prop':'revisions',
              'titles':page.name,
              'rvlimit':'10'
              }
    res = site.api(**params)
    pageid = next(iter(res['query']['pages']))
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
            timestamp = datetime.datetime.strptime(
                timestamp, '%Y-%m-%dT%H:%M:%SZ'
            ).replace(tzinfo=datetime.UTC)
            if timestamp < datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=7):
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
              'titles':page.name,
              'formatversion':'2',
              'iiprop':'size'
              }
    res = site.api(**params)
    pixel = res['query']['pages'][0]['imageinfo'][0]['width'] * res['query']['pages'][0]['imageinfo'][0]['height']
    if pixel > 105000:
    #if (res['query']['pages'][0]['imageinfo'][0]['width'] > 400) and (res['query']['pages'][0]['imageinfo'][0]['height'] > 400):
        pnt('chacksize manual')
        return "Manual"
    else:
        return True

def addmanual(pagetext,file): #Just makes it a bit shorter
    pagetext = re.sub(r'[Nn]on-free reduced', 'Orphaned non-free revisions', pagetext)
    pagetext = re.sub(r'(?P<Main>\{\{(?:[Oo]rphaned non-free revisions|[Nn]on-free reduced).*?(?=}}))', r'\g<Main>|human=yes', pagetext)
    pnt("Requesting manual review on " + file)
    return pagetext

def main():
    pnt("main: starting run")
    tobreak = "no"
    pages = findpages()
    pnt(f"main: {len(pages)} pages to process")
    for filep in pages: #For page in the list
        if tobreak == "yes":
            break
        try: #Try to delete the old revision(s)
            if filep.name == "Category:Non-free files with orphaned versions more than 7 days old needing human review": #Skip category thing
                continue
            pnt(f"Processing {filep.page_title}")
            todelete = versiontodelete(filep)
            pnt(f"Found {len(todelete)} revisions for {filep.page_title}")
            firstversion="yes"
            for version in todelete:
                version = version['archivename']
                go = startAllowed() #Check if task is enabled
                if go == "no":
                    tobreak = "yes"
                    break
                if firstversion == "yes":
                    pagepage = site.pages[filep.name]
                    pagetext = pagepage.text()
                    #Stop if there's nobots
                    allow_bots(pagetext, "DeltaQuadBot")
                    skipcategories = site.pages['User:RonBot/1/FreeCategory'].text().split("|")
                    check = abusechecks(filep) #Check if file was uploaded 2 days ago
                    page_categories = {cat.name for cat in pagepage.categories()}
                    if any(skipcategory in page_categories for skipcategory in skipcategories):
                        pnt("One of the potentially free categories were found. Skipping.")
                        check="free"
                    if check == "No":
                        if pagetext.find('|human=yes')>0:break#Manual already set - no more to do
                        pagetext = addmanual(pagetext,filep.name)
                        pagepage.edit(text=pagetext, summary="(Image Revdel) Requesting manual review ([[User:AmandaNP/Imagerevdel/Run|disable]])", bot=True) #(DO NOT UNCOMMENT UNTIL BOT IS APPROVED)
                        break #- leave for loop as we only want one entry - there may be multple versions to delete
                    if check == "free":
                        if pagetext.find('|human=yes')>0:break#Manual already set - no more to do
                        pagetext = addmanual(pagetext,filep.name)
                        pagepage.edit(text=pagetext, summary="(Image Revdel) Requesting manual review - Free file conflict ([[User:AmandaNP/Imagerevdel/Run|disable]])", bot=True) #(DO NOT UNCOMMENT UNTIL BOT IS APPROVED)
                        break #- leave for loop as we only want one entry - there may be multple versions to delete
                    if  (filep) == "Manual":
                        if pagetext.find('|human=yes')>0:break#Manual already set - no more to do
                        pagetext = addmanual(pagetext,filep.name)
                        pagepage.edit(text=pagetext, summary="(Image Revdel) Requesting manual review ([[User:AmandaNP/Imagerevdel/Run|disable]])", bot=True) #(DO NOT UNCOMMENT UNTIL BOT IS APPROVED)
                        break #- leave for loop as we only want one entry - there may be multple versions to delete
                token = site.get_token('csrf')
                #Delete the revision
                deletefile(filep, version, token)
                #Remove tag
                pagetext = re.sub(r'\n*\{\{(?:[Oo]rphaned non-free revisions|[Nn]on-free reduced).*}}', '', pagetext)
                pagetext=pagetext.lstrip()
                pagepage.edit(text=pagetext, summary="(Image Revdel) Orphaned non-free file(s) deleted per [[WP:F5|F5]] ([[User:AmandaNP/Imagerevdel/Run|disable]])", bot=True) #(DO NOT UNCOMMENT UNTIL BOT IS APPROVED)
                pnt ("Revdel complete for %s" % filep.name) #For debugging
                firstversion="no"
            else:
                pagepage = site.pages[filep.name]
                pagetext = pagepage.text()
                pagetext = re.sub(r'\n*\{\{(?:[Oo]rphaned non-free revisions|[Nn]on-free reduced).*}}', '', pagetext)
                pagetext=pagetext.lstrip()
                pagepage.edit(text=pagetext, summary="(Image Revdel) Remove banner - nothing to delete ([[User:AmandaNP/Imagerevdel/Run|disable]])", bot=True) #(DO NOT UNCOMMENT UNTIL BOT IS APPROVED)

        except Exception as e: #If there's an error, ignore the file
            print(e)
            pass
def startAllowed():
    textpage = site.pages["User:AmandaNP/Imagerevdel/Run"].text()
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
