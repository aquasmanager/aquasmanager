def test_language_preference_follows_the_account(api, client, uid):
    api.post("/register", {"username": f"lang{uid}", "password": "Password123!", "role": "consult",
                           "must_change_password": False}, code=201)
    login = client.post("/login", data={"username": f"lang{uid}", "password": "Password123!"}).json()
    assert login["language"] is None  # pas encore choisie : celle de l'appareil s'applique
    headers = {"Authorization": f"Bearer {login['access_token']}"}

    assert client.put("/me/language", json={"language": "en"}, headers=headers).json() == {"language": "en"}
    assert client.get("/me", headers=headers).json()["language"] == "en"
    # Gardée pour la prochaine connexion (autre appareil)
    assert client.post("/login", data={"username": f"lang{uid}", "password": "Password123!"}).json()["language"] == "en"
    assert client.put("/me/language", json={"language": "de"}, headers=headers).status_code == 422
