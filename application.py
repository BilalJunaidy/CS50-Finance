import os

from cs50 import SQL
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions, HTTPException, InternalServerError
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@app.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.route("/")
@login_required
def index():
            """Show portfolio of stocks"""
            current_balance = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])
            current_balance = current_balance[0]["cash"]

            index_row = db.execute("SELECT SUM(share_quantity), symbol, company_name FROM TRANSACTIONS WHERE user_id = :user_id GROUP BY symbol",
            user_id = session["user_id"])

            total_portfolio = 0

            for row in index_row:
                lookup_return = lookup(row["symbol"])
                row["current_price"] = (lookup_return["price"])
                row["total"] = (row["SUM(share_quantity)"] * row["current_price"])
                total_portfolio += int(row["total"])
                row["current_price"] = usd(row["current_price"])
                row["total"] = usd(row["total"])

            total = usd(total_portfolio + current_balance)

            return render_template("portfolio.html", row = index_row, cash = usd(current_balance), total = total, user = session["user_name"])


#    return apology("TOsDO")


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
        """Buy shares of stock"""
        if request.method == "GET":
            return render_template("buy.html", user = session["user_name"])
        else:
            lookup_return = lookup(request.form.get("symbol"))
            lookup_return_price = float(lookup_return["price"])
            current_balance = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])[0]["cash"]
            current_balance = float(current_balance)
            number_of_shares_bought = int(request.form.get("shares"))
            cash_after = current_balance - lookup_return_price * float(number_of_shares_bought)


            if not request.form.get("symbol"):
                return apology("Mate this is not a guess game, u gotta tell me what u wanna buy", 400)
            elif not request.form.get("shares"):
                return apology("Mate, you can't buy 0 of something", 400)
            elif int(request.form.get("shares")) < 1:
                return apology("Shares must be greater than or equal to 1", 400)
            elif lookup_return == None:
                return apology("invalid symbol", 400)
            elif cash_after < 0:
                return apology("u iz broke son", 400)
            else:
                db.execute("CREATE TABLE IF NOT EXISTS TRANSACTIONS ('symbol' TEXT NOT NULL, 'company_name' TEXT NOT NULL, 'share_quantity' NUMERIC NOT NULL, 'share_price' NUMERIC NOT NULL, 'timestamp' TEXT NOT NULL, 'user_id' INTEGER NOT NULL, FOREIGN KEY('user_id') REFERENCES users('id'))")
                now = datetime.now()
                timestamp = now.strftime("%d/%m/%Y %H:%M:%S")
                db.execute("INSERT INTO TRANSACTIONS (symbol, company_name, share_quantity, share_price, timestamp, user_id) VALUES(?,?,?,?,?,?)",
                (lookup_return['symbol'], lookup_return['name'], int(request.form.get('shares')), lookup_return['price'], timestamp, session["user_id"]))

                db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=cash_after, id = session["user_id"])

                #Redirect user to index page with a success message
                flash("Bought!")
                return redirect("/")

@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    history = db.execute("SELECT * FROM TRANSACTIONS WHERE user_id =:user_id", user_id = session["user_id"])
    for row in history:
        row["share_price"] = usd(row["share_price"])

    return render_template("history.html", history = history, user = session["user_name"])

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
        rows = db.execute("SELECT * FROM users WHERE username = :username",
                          username=request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["user_name"] = rows[0]["username"]

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
        cash = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])[0]["cash"]
        return render_template("quote.html", cash = usd(cash), user = session["user_name"])
    else:
        lookup_return = lookup(request.form.get("symbol"))
        if not request.form.get("symbol"):
            return apology("Please provide symbol", 400)
        elif lookup_return == None:
            return apology("Invalid symbol", 400)
        else:
            return render_template("quoted.html", name = lookup_return["name"], symbol = lookup_return["symbol"], price = usd(lookup_return["price"]), user = session["user_name"])

    #return apology("TODO")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""

    session.clear()

    if request.method == "GET":
        return render_template("register.html")
    else:
        username_provided = request.form.get("username")
        username_list = db.execute("SELECT * FROM users WHERE username = :username",
                          username=username_provided)

        if not request.form.get("username"):
            return apology("username not provided", 400)
        elif not request.form.get("password"):
            return apology("password not provided", 400)
        elif not request.form.get("confirmation"):
            return apology("confirmation password not provided", 400)
        elif request.form.get("password") != request.form.get("confirmation"):
            return apology("passwords must match", 400)
        elif len(username_list) == 1:
            return apology("username not available", 400)
        else:
            hash = generate_password_hash(request.form.get("password"))
            db.execute("INSERT INTO users (username, hash) VALUES (?, ?)",
            (username_provided, hash))

            # Redirect user to home page
            return redirect("/")

        #return apology("TODO")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    if request.method == "GET":
        symbol_list = db.execute("SELECT DISTINCT(symbol) from TRANSACTIONS WHERE user_id = :user_id", user_id = session["user_id"])
        return render_template("sell.html", symbol_list = symbol_list, user = session["user_name"])
    else:
        number_of_shares = db.execute("SELECT SUM(share_quantity) FROM TRANSACTIONS WHERE user_id =:user_id AND symbol =:symbol", user_id = session["user_id"], symbol = request.form.get("symbol"))
        lookup_return = lookup(request.form.get("symbol"))
        lookup_return_price = float(lookup_return["price"])
        current_balance = db.execute("SELECT cash FROM users WHERE id = :id", id = session["user_id"])[0]["cash"]
        current_balance = float(current_balance)
        number_of_shares_sold = int(request.form.get("shares"))
        cash_after = current_balance + lookup_return_price * float(number_of_shares_sold)

        if not request.form.get("symbol"):
            return apology("Symbol missing", 400)
        elif not request.form.get("shares"):
            return apology("Shares missing", 400)
        elif number_of_shares[0]["SUM(share_quantity)"] < int(request.form.get('shares')):
            return apology("You can't sell what you don't have mate", 400)
        else:
            now = datetime.now()
            timestamp = now.strftime("%d/%m/%Y %H:%M:%S")
            db.execute("INSERT INTO TRANSACTIONS (symbol, company_name, share_quantity, share_price, timestamp, user_id) VALUES(?,?,?,?,?,?)",
            (lookup_return['symbol'], lookup_return['name'], -int(request.form.get('shares')), lookup_return['price'], timestamp, session["user_id"]))

            db.execute("UPDATE users SET cash = :cash WHERE id = :id", cash=cash_after, id = session["user_id"])

            #Redirect user to index page with a success message
            flash("Sold!")
            return redirect("/")


def errorhandler(e):
    """Handle error"""
    if not isinstance(e, HTTPException):
        e = InternalServerError()
    return apology(e.name, e.code)


# Listen for errors
for code in default_exceptions:
    app.errorhandler(code)(errorhandler)
