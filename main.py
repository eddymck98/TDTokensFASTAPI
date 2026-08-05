from routers import auth, bets, profile

app.include_router(auth.router)
app.include_router(bets.router)
app.include_router(profile.router)
