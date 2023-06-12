import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    # get user_id from sessions
    user_id = session["user_id"]
    # get all stock info from transactions table, use sum function for share number total
    stocks = db.execute("SELECT symbol, name, price, SUM(shares) as total_shares FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
    # get available cash from user table
    cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

    # declare total cash variable
    total_cash = cash
    # loop through stocks and sum total_cash
    for stock in stocks:
        total_cash += stock["price"] * stock["total_shares"]

    return render_template("index.html", stocks=stocks, cash=cash, total=total_cash, usd=usd)


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""

    # GET method
    if request.method == "GET":
        return render_template("buy.html")

    # POST method starts
    # variable declarations
    symbol = request.form.get("symbol").upper()
    shares = int(request.form.get("shares"))
    stock = lookup(symbol)
    user_id = session["user_id"]

    # few apologies
    if not symbol:
        return apology("Please provide a symbol for quote")
    if not stock:
        return apology("Your symbol does not exist")
    if shares < 0:
        return apology("Number of shares must be a positive number")

    # cash available for user
    old_cash = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

    # cost of buying shares
    shares_cost = shares * stock["price"]

    # not enough money to buy
    if old_cash < shares_cost:
        return apology("Sorry, not enough money in your account")

    # enough money to buy
    new_cash = old_cash - shares_cost
    # set new cash in user table
    db.execute("UPDATE users SET cash = ? WHERE id = ?", new_cash, user_id)
    # insert buy into trasaction table
    db.execute("INSERT INTO transactions (user_id, name, shares, price, type, symbol) VALUES (?, ?, ?, ?, ?, ?)",
     user_id, stock["name"], shares, stock["price"], "BOUGHT", symbol)

    # message that transaction complete
    flash("your buying is complete")

    return redirect("/")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    # get user_id from session
    user_id = session["user_id"]
    # get transaction history from transactions table
    trans_history = db.execute("SELECT symbol, price, shares, type, time FROM transactions WHERE user_id = ?", user_id)
    # pass it client side including the usd formatting function
    return render_template("history.html", trans_history=trans_history, usd=usd)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "GET":
        return render_template("quote.html")
    else:
        symbol = request.form.get("symbol")
        if not symbol:
            return apology("Please provide a symbol for quote")
        stock = lookup(symbol.upper())
        if not stock:
            return apology("Your symbol does not exist")
        return render_template("quoted.html", name = stock["name"], price = stock["price"], symbol = stock["symbol"])


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    # GET method
    if request.method == "GET":
        return render_template("register.html")
    # POST method
    else:
        username = request.form.get("username")
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("Please provide an username")
        if not password:
            return apology("Please provide a password")
        if not confirmation:
            return apology("Please same password for confirmation")
        if password != confirmation:
            return apology("Your passwords do not match")

        hash = generate_password_hash(password)

        try:
            new_user = db.execute("INSERT INTO users (username, hash) VALUES (?, ?)", username, hash)
        except:
            return apology("This username already exists")

        # put user in session so they do not have to go back to login to enter the site
        # same as login
        session["user_id"] = new_user
        return redirect("/")




@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    # get the user_id from sessions
    user_id = session["user_id"]

    # GET method starts here
    if request.method == "GET":
        # get the symbols of stocks the user has from transactions table
        symbols = db.execute("SELECT symbol FROM transactions WHERE user_id = ? GROUP BY symbol", user_id)
        #  returning the symbols dictionary to the sell.html page
        return render_template("sell.html", symbols = symbols)

    # POST method starts here
    # get symbol and number of shares from the form on sell.html
    symbol = request.form.get("symbol")
    shares = int(request.form.get("shares"))

    # we make sure number of shares are not negative
    if shares < 0:
        return apology("Number of shares must be a positive number")

    # get stock name and price from API using lookup function
    stock_name = lookup(symbol)["name"]
    stock_price = lookup(symbol)["price"]
    # and check how many shares currently owned of the same symbol before allowing to sell
    shares_curr_owned = db.execute("SELECT shares FROM transactions WHERE user_id = ? AND symbol = ? GROUP BY symbol",
    user_id, symbol)[0]["shares"]
    if shares_curr_owned < shares:
        return apology("You currently do not own enough shares to sell")

    # get current cash balance so we can update it after selling
    cash_balance = db.execute("SELECT cash FROM users WHERE id = ?", user_id)[0]["cash"]

    # updating cash balance
    cash_update = cash_balance + (shares * stock_price)
    db.execute("UPDATE users SET cash = ? WHERE id = ?", cash_update, user_id)

    # updating transactions table with current selling of stocks
    db.execute("INSERT INTO transactions (user_id, name, shares, price, type, symbol) VALUES (?, ?, ?, ?, ?, ?)",
    user_id, stock_name, -shares, stock_price, "SOLD", symbol)

    return redirect("/")