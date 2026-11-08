import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.services.state_factory import StateFactory
from app.graph.workflow import workflow
from app.api.schemas import SolveRequest


router = APIRouter()


@router.post("/generate/stream")
async def generate_stream(request: SolveRequest):

    async def event_generator():

        try:
            initial_state = StateFactory.create(
                request.problem,
                request.acceptance_score,
            )

            async for event in workflow.astream(
                initial_state,
                stream_mode="updates",
            ):
                print(event)

                for agent, data in event.items():

                    payload = {
                        "agent": agent,
                        "status": "completed",
                        "data": data,
                    }

                    yield f"data: {json.dumps(payload, default=str)}\n\n"

            yield f"data: {json.dumps({
                'status': 'completed'
            })}\n\n"

        except Exception as e:

            import traceback
            traceback.print_exc()

            yield f"data: {json.dumps({
                'status': 'error',
                'error': str(e)
            })}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )