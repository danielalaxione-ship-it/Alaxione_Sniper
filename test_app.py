from app import extract_reviews, generate_pitch

# Mocking extract_reviews for testing would be more complex, but we can test generate_pitch

def test_generate_pitch_no_reviews():
    pitch = generate_pitch([], note=4.5, count=100)
    assert "Aucun avis textuel n'a pu être extrait" in pitch
    assert "les patients du praticien" in pitch
    print("test_generate_pitch_no_reviews passed")

def test_generate_pitch_no_stats():
    pitch = generate_pitch(["Tout est parfait, merci beaucoup !"], note=5, count=10)
    assert "Aucune tendance de point de douleur majeure" in pitch
    print("test_generate_pitch_no_stats passed")

def test_generate_pitch_with_stats():
    pitch = generate_pitch(["Le temps d'attente est vraiment long et le téléphone ne répond jamais.", "Annulation de dernière minute"], note=2, count=3)
    assert "retard ou de temps d'attente" in pitch
    assert "joindre le secrétariat par téléphone" in pitch
    assert "annulations" in pitch
    print("test_generate_pitch_with_stats passed")

test_generate_pitch_no_reviews()
test_generate_pitch_no_stats()
test_generate_pitch_with_stats()
