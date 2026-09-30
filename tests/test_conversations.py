import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.embeddings.local import SentenceTransformerEmbeddingProvider
from app.llm.mock import MockLLMProvider
from app.main import app
from app.core.database import get_db
from app.models.conversation import Conversation, Message, MessageRole
from app.retrieval.vector import VectorRetriever
from app.services.conversation import ConversationService
from app.services.ingestion import DocumentIngestionService
from app.services.rag import RAGService


@pytest.fixture
def client(db_session: Session) -> TestClient:
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def populated_conversation_kb(db_session: Session):
    provider = SentenceTransformerEmbeddingProvider(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        dimension=384,
    )
    ingestion_service = DocumentIngestionService(embedding_provider=provider)

    doc_text = (
        "Employee Benefits & Leave Policy.\n\n"
        "All full-time employees receive 20 days of annual paid time off.\n\n"
        "Up to 5 unused PTO days can be carried forward into the next calendar year.\n\n"
        "Maternity leave covers 16 weeks of fully paid leave."
    ).encode("utf-8")

    doc, ver, _, chunks = ingestion_service.process_and_ingest_document(
        db=db_session,
        file_bytes=doc_text,
        filename="leave_policy.txt",
        name="Employee Leave Policy",
        owner_id="usr_hr_lead",
        chunk_size=100,
        chunk_overlap=20,
    )

    return {
        "provider": provider,
        "document": doc,
        "version": ver,
        "chunks": chunks,
    }


class TestConversationService:
    def test_conversation_creation(self, db_session: Session):
        conv = ConversationService.create_conversation(
            db=db_session,
            user_id="usr_alice",
            title="Benefits Inquiry",
        )
        assert conv.id is not None
        assert conv.user_id == "usr_alice"
        assert conv.title == "Benefits Inquiry"
        assert conv.created_at is not None
        assert conv.updated_at is not None

    def test_message_creation_and_ordering(self, db_session: Session):
        conv = ConversationService.create_conversation(db=db_session, user_id="usr_bob")

        msg1 = Message(conversation_id=conv.id, role=MessageRole.USER, content="Hello")
        msg2 = Message(conversation_id=conv.id, role=MessageRole.ASSISTANT, content="Hi! How can I help?")
        msg3 = Message(conversation_id=conv.id, role=MessageRole.USER, content="Tell me about PTO")

        db_session.add_all([msg1, msg2, msg3])
        db_session.commit()

        # Retrieve and verify chronological order
        history = ConversationService.get_recent_history(db=db_session, conversation_id=conv.id, max_turns=5)
        assert len(history) == 3
        assert history[0]["role"] == "user"
        assert history[0]["content"] == "Hello"
        assert history[1]["role"] == "assistant"
        assert history[1]["content"] == "Hi! How can I help?"
        assert history[2]["role"] == "user"
        assert history[2]["content"] == "Tell me about PTO"

    def test_conversation_retrieval_and_listing(self, db_session: Session):
        conv1 = ConversationService.create_conversation(db=db_session, user_id="usr_carol", title="Conv 1")
        conv2 = ConversationService.create_conversation(db=db_session, user_id="usr_carol", title="Conv 2")

        # List Carol's conversations
        carol_convs = ConversationService.list_conversations(db=db_session, user_id="usr_carol")
        assert len(carol_convs) == 2
        titles = [c.title for c in carol_convs]
        assert "Conv 1" in titles
        assert "Conv 2" in titles

        # Get specific conversation
        fetched = ConversationService.get_conversation(db=db_session, conversation_id=conv1.id)
        assert fetched is not None
        assert fetched.id == conv1.id

    def test_multiple_conversations_isolation(self, db_session: Session):
        conv1 = ConversationService.create_conversation(db=db_session, user_id="usr_user1")
        conv2 = ConversationService.create_conversation(db=db_session, user_id="usr_user2")

        msg1 = Message(conversation_id=conv1.id, role=MessageRole.USER, content="User1 private query")
        msg2 = Message(conversation_id=conv2.id, role=MessageRole.USER, content="User2 private query")

        db_session.add_all([msg1, msg2])
        db_session.commit()

        hist1 = ConversationService.get_recent_history(db=db_session, conversation_id=conv1.id)
        hist2 = ConversationService.get_recent_history(db=db_session, conversation_id=conv2.id)

        assert len(hist1) == 1
        assert hist1[0]["content"] == "User1 private query"
        assert len(hist2) == 1
        assert hist2[0]["content"] == "User2 private query"

    def test_multi_turn_rag_interaction(
        self, db_session: Session, populated_conversation_kb: dict
    ):
        provider = populated_conversation_kb["provider"]
        retriever = VectorRetriever(db=db_session, embedding_provider=provider)
        llm = MockLLMProvider()
        rag_service = RAGService(retriever=retriever, llm_provider=llm)

        conv = ConversationService.create_conversation(db=db_session, user_id="usr_multi")

        # Turn 1: Initial Question
        user_msg1, asst_msg1, rag_res1 = ConversationService.send_message_and_generate_response(
            db=db_session,
            conversation_id=conv.id,
            user_content="What is the annual PTO allowance?",
            rag_service=rag_service,
        )

        assert user_msg1.role == MessageRole.USER
        assert asst_msg1.role == MessageRole.ASSISTANT
        assert rag_res1.is_grounded is True
        assert len(rag_res1.sources) > 0

        # Turn 2: Follow-up question relying on context
        user_msg2, asst_msg2, rag_res2 = ConversationService.send_message_and_generate_response(
            db=db_session,
            conversation_id=conv.id,
            user_content="How many days can be carried forward?",
            rag_service=rag_service,
        )

        assert user_msg2.role == MessageRole.USER
        assert asst_msg2.role == MessageRole.ASSISTANT
        assert rag_res2.is_grounded is True

        # Verify conversation history now contains all 4 messages
        history = ConversationService.get_recent_history(db=db_session, conversation_id=conv.id)
        assert len(history) == 4
        assert history[0]["content"] == "What is the annual PTO allowance?"
        assert history[2]["content"] == "How many days can be carried forward?"


class TestConversationAPI:
    def test_conversation_api_flow(self, client: TestClient, populated_conversation_kb: dict):
        # 1. Create conversation
        create_res = client.post(
            "/api/v1/conversations",
            json={"user_id": "usr_api_user", "title": "API Test Chat"},
        )
        assert create_res.status_code == 201
        conv_data = create_res.json()
        conv_id = conv_data["id"]

        # 2. List conversations
        list_res = client.get(f"/api/v1/conversations?user_id=usr_api_user")
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 1

        # 3. Post a message to conversation
        msg_payload = {
            "content": "What is the policy on maternity leave?",
            "top_k": 3,
        }
        msg_res = client.post(f"/api/v1/conversations/{conv_id}/messages", json=msg_payload)
        assert msg_res.status_code == 200
        msg_data = msg_res.json()
        assert msg_data["conversation_id"] == conv_id
        assert msg_data["is_grounded"] is True
        assert len(msg_data["sources"]) > 0

        # 4. Get conversation detail with history
        detail_res = client.get(f"/api/v1/conversations/{conv_id}")
        assert detail_res.status_code == 200
        detail_data = detail_res.json()
        assert len(detail_data["messages"]) == 2  # user + assistant
        assert detail_data["messages"][0]["role"] == "user"
        assert detail_data["messages"][1]["role"] == "assistant"
