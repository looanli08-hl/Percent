import numpy as np

from engram.models import FindingCategory, Fragment
from engram.persona.fragments import FragmentStore


def test_store_and_retrieve_fragment(tmp_engram_dir):
    store = FragmentStore(tmp_engram_dir / "fragments.db")
    fragment = Fragment(
        category=FindingCategory.OPINION,
        content="Thinks The Three-Body Problem Book 1 is the best",
        confidence=0.9,
        source="wechat",
        embedding=np.random.rand(384).tolist(),
    )
    stored = store.add(fragment)
    assert stored.id is not None
    retrieved = store.get(stored.id)
    assert retrieved.content == fragment.content


def test_search_fragments_by_similarity(tmp_engram_dir):
    store = FragmentStore(tmp_engram_dir / "fragments.db")
    target_embedding = np.array([1.0, 0.0, 0.0])

    store.add(Fragment(
        category=FindingCategory.OPINION,
        content="Loves sci-fi novels",
        confidence=0.9, source="wechat",
        embedding=[0.9, 0.1, 0.0],
    ))
    store.add(Fragment(
        category=FindingCategory.PREFERENCE,
        content="Prefers spicy food",
        confidence=0.8, source="wechat",
        embedding=[0.0, 0.0, 1.0],
    ))

    results = store.search(target_embedding.tolist(), top_k=1)
    assert len(results) == 1
    assert "sci-fi" in results[0].content


def test_get_all_fragments(tmp_engram_dir):
    store = FragmentStore(tmp_engram_dir / "fragments.db")
    store.add(Fragment(category=FindingCategory.TRAIT, content="Introverted",
                       confidence=0.8, source="wechat", embedding=[1.0]))
    store.add(Fragment(category=FindingCategory.HABIT, content="Night owl",
                       confidence=0.7, source="bilibili", embedding=[0.0]))
    all_frags = store.get_all()
    assert len(all_frags) == 2


def test_stats(tmp_engram_dir):
    store = FragmentStore(tmp_engram_dir / "fragments.db")
    store.add(Fragment(category=FindingCategory.TRAIT, content="a",
                       confidence=0.8, source="wechat", embedding=[1.0]))
    store.add(Fragment(category=FindingCategory.OPINION, content="b",
                       confidence=0.7, source="bilibili", embedding=[0.0]))
    stats = store.stats()
    assert stats["total"] == 2
    assert stats["by_source"]["wechat"] == 1
    assert stats["by_source"]["bilibili"] == 1
