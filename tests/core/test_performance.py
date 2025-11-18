import random
import time

import pytest

from ao3_helper.core.analysis_engine import AnalysisEngine


@pytest.mark.slow
def test_analysis_engine_performance():
    """
    Stress test: Popola l'engine con 5000 fic e misura il tempo di ricalcolo.
    Obiettivo: full_recalculation deve stare sotto 1.5 secondi (su CPU moderna).
    """
    engine = AnalysisEngine()

    dataset = []
    fandoms_pool = [f"Fandom {i}" for i in range(50)]
    tags_pool = [f"Tag {i}" for i in range(200)]
    authors_pool = [f"Author {i}" for i in range(100)]

    for i in range(5000):
        dataset.append(
            {
                "title": f"Fic {i}",
                "author": random.choice(authors_pool),
                "fandoms": random.choice(fandoms_pool),
                "tags": ", ".join(random.sample(tags_pool, 3)),
                "status": random.choice(["Read", "To Read", "Kudosed"]),
                "user_rating": random.randint(0, 5),
                "is_in_library": True,
                "is_in_history": bool(random.getrandbits(1)),
                "visit_count": random.randint(1, 10),
            }
        )

    start_time = time.time()

    for fic in dataset:
        engine.add_fic(fic)

    results = engine.get_analysis_results()

    end_time = time.time()
    duration = end_time - start_time

    print(f"\nPerformance: Processed 5000 fics in {duration:.4f} seconds.")

    assert len(results["authors"]) > 0
    assert duration < 2.0, f"Analysis Engine è troppo lento! {duration}s > 2.0s"
