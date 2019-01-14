import sys
from utils import slugify
from quart import (abort, Quart, g, redirect, render_template, request, session, url_for)
from tinymongo import TinyMongoClient
from passlib.hash import sha256_crypt
    
app = Quart(__name__)
app.secret_key = 'J*Hhw7Hk^%dfjL'
DB = TinyMongoClient().blog
BRAND = 'MiniCMS'
@app.errorhandler(404)
async def page_not_found(e):
    """404 error handler-- 404 status set explicitly"""
    return await render_template('404.html'), 404

@app.route('/login', methods=['GET','POST'])
async def login():
    """a simple login form check the hashed password"""
    status = None
    if request.method == 'POST':
        username = (await request.form).get('username')
        password = (await request.form).get('password')
        # do a lookup of the username
        user = DB.user.find_one({'username': username})
        if user:
            if sha256_crypt.verify(password, user.get('password')):
                session['logged_in'] = True
                return redirect(url_for('index'))
            
        status = 'Failed username/password'
    return await render_template('login.html', status=status)

@app.route('/logout')
def logout():
    # clear session cookie
    session.pop('logged_in', None)
    return redirect(url_for('index'))
    
@app.route('/index')
async def index():
    """return all the pages to a user view"""
    # get all pages
    g.brand = BRAND
    pages = DB.blog.find()
    return await render_template('page_list.html', pages=pages)

@app.route('/view/<id>')
async def page_view(id):
    """view a page by id or 404 if does not exist"""
    # lookup page by its TinyMongo id
    g.brand = BRAND
    page = DB.blog.find_one({'_id':id})
    if page is None:
        # return a 404 error page does not exist
        abort(404)
    
    return await render_template('view.html', page=page)


@app.route('/edit', methods=['GET','POST'])
@app.route('/edit/<id>', methods=['GET','POST'])
async def page_edit(id=None):
    """edit serves to edit an existing page with a particular id, or create a new page"""
    
    if not(session.get('logged_in')):
        # if not logged it, dump them back to index
        return redirect(url_for('index'))
        
    status = ''
    if id:
        # find the page by its id, if it doesn't exist page = None, abort to 404 page
        page = DB.blog.find_one({'_id':id})
        if page is None:
            abort(404)
    else:
        # new page starts as a blank document
        status = 'Creating a new page.'
        page = {'title': '', 'slug':'', 'content': ''}
    
    if request.method == 'POST':
        # check if user cancel was pressed.
        if (await request.form)['submit'] == 'cancel':
            if id:
                # user canceled a page edit, return to page view
                return redirect(url_for('page_view', id=id))
            else:
                # user canceled a new page creation, return to index
                return redirect(url_for('index'))
            
        # user hit submit, so get the data from the form.
        page['title'] = (await request.form).get('title')
        page['slug'] = (await request.form).get('slug')
        page['content'] = (await request.form).get('editordata')
        # look for required title and content
        if page['title'] != '' and page['content'] != '':
            # now, update or insert into database
            if not(page.get('slug')):
                # make a slug if user left it out.
                page['slug'] = slugify(page.get('title'))
            if id:
                # update an existing page
                DB.blog.update_one({'_id':id}, page)
            else:
                # insert a new page and get its id.
                id = DB.blog.insert_one(page).inserted_id
            # redirect to page view
            return redirect(url_for('page_view', id=id))
        else:
            # indicate a failure to enter required data
            status = 'ERROR: page title and content are required!'
        
    return await render_template('edit.html', page=page, status=status)

@app.route('/delete/<id>')
async def page_delete(id):
    """delete a page of a particular id, and return to top-level index"""
    
    if not(session.get('logged_in')):
        # if not logged it, dump them back to index
        return redirect(url_for('index'))
    
    page = DB.blog.find_one({'_id':id})
    if page is None:
        abort(404)
    
    DB.blog.delete_one({'_id':id})
    return redirect(url_for('index'))

@app.route('/search')
async def search():
    return redirect(url_for('index'))

# this is the general SITE route "catchment" for page view
@app.route("/")
@app.route("/<path:path>")
async def site(path=None):
    """view for pages referenced via their slug (which can look like a path
    If you want to modify what happens when an empty path comes in
    See below, it is redirected to "index" view.  This can be changed via code below.
    """
    # uncomment the three lines if you have a search box
    #s = (await request.args).get('s','')
    #if s:
    #    return redirect( url_for('search', s=s) )

    g.brand = BRAND
    if path is None:
        """modify here to change behavior of the home-index"""
        path = 'home'

    page = DB.blog.find_one({'slug': path})
    if page is None:
        abort(404)
    
    return await render_template('view.html', page=page)

    
def init_db():
    user = DB.user.find()
    if user.count() < 1:
        admin = 'blogger'
        password = 'secret?'
        print('creating an blog admin username={} password={}'.format(admin, password))
        hashed = sha256_crypt.encrypt(password)
        DB.user.insert_one({'username': admin, 'password': hashed})
        
    page = DB.blog.find_one({'slug':'home'})
    if page is None:
        default_index = {
            'slug':'home',
            'title':'Default Homepage',
            'content': """
            Sed ut perspiciatis unde omnis iste natus error sit voluptatem accusantium doloremque laudantium, totam rem aperiam, eaque ipsa quae ab illo inventore veritatis et quasi architecto beatae vitae dicta sunt explicabo. Nemo enim ipsam voluptatem quia voluptas sit aspernatur aut odit aut fugit, sed quia consequuntur magni dolores eos qui ratione voluptatem sequi nesciunt. Neque porro quisquam est, qui dolorem ipsum quia dolor sit amet, consectetur, adipisci velit, sed quia non numquam eius modi tempora incidunt ut labore et dolore magnam aliquam quaerat voluptatem. Ut enim ad minima veniam, quis nostrum exercitationem ullam corporis suscipit laboriosam, nisi ut aliquid ex ea commodi consequatur? Quis autem vel eum iure reprehenderit qui in ea voluptate velit esse quam nihil molestiae consequatur, vel illum qui dolorem eum fugiat quo voluptas nulla pariatur?
            """
        }
        DB.blog.insert_one(default_index)

def arg_val(arg):
    """gets value associated with CLI switch, returns None if arg not found, True if found with no trailing value"""
    idx = sys.argv.index(arg)
    if idx < 0:
        return None
    try:
        # return next argument
        return sys.argv[idx + 1]
    except:
        # since there was no next argument, return true
        return True
    
if __name__ == '__main__':
    # note: app.run should not be used in production for a variety of reasons.
    port = 5000
    
    
    init_db()
    
    if '--createuser' in sys.argv:
        """create a new user from the command line interface"""
        admin = input("Enter blogger admin username: ")
        password = input("Enter blogger admin password: ")
        hashed = sha256_crypt.encrypt(password)
        DB.user.insert_one({'username': admin, 'password': hashed})
        print("User has been created.")
        sys.exit(0)
        
    if '--users' in sys.argv:
        """list users in the user database to the console"""
        users = DB.user.find()
        for user in users:
            print("username: {}".format(user['username']))
        print("done.")
        sys.exit(0)
        
    if '--deleteuser' in sys.argv:
        """delete a named user"""
        username = arg_val('--deleteuser')
        user = DB.user.find_one({'username':username})
        if user:
            DB.user.delete_one({'_id':user.get('_id')})
            print("User '{}' deleted".format(user.get('username')))
        else:
            print("User '{}' not found".format(username))
        sys.exit(0)
        
    if '--port' in sys.argv:
        """change the deployment port"""
        port = int(sys.argv[sys.argv.index('--port')+1])
    
    # run the server
    app.run(port=port, host='0.0.0.0')
