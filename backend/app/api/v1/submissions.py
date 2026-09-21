from flask import Blueprint, request
from flask_restful import Api, Resource

from app.auth.decorators import permission_required
from app.extensions import db
from app.models.community import StorySubmission
from app.schemas.community import ReviewStatusInputSchema, StorySubmissionInputSchema, StorySubmissionSchema
from app.utils.pagination import paginate
from app.utils.responses import ApiError, success_response

submissions_bp = Blueprint("submissions", __name__)
api = Api(submissions_bp)

submission_schema = StorySubmissionSchema()


class SubmissionListResource(Resource):
    @permission_required("submissions.manage")
    def get(self):
        query = StorySubmission.query.order_by(StorySubmission.submitted_at.desc())
        status = request.args.get("status")
        if status:
            query = query.filter_by(status=status)
        result = paginate(query, submission_schema)
        return success_response(result["items"], meta=result["meta"])

    def post(self):
        data = StorySubmissionInputSchema().load(request.get_json(silent=True) or {})
        submission = StorySubmission(**data)
        db.session.add(submission)
        db.session.commit()
        return success_response(submission_schema.dump(submission), status=201)


class SubmissionStatusResource(Resource):
    @permission_required("submissions.manage")
    def patch(self, submission_id):
        submission = db.session.get(StorySubmission, submission_id)
        if submission is None:
            raise ApiError("Submission not found.", 404, code="not_found")

        data = ReviewStatusInputSchema().load(request.get_json(silent=True) or {})
        submission.status = data["status"]
        db.session.commit()
        return success_response(submission_schema.dump(submission))


api.add_resource(SubmissionListResource, "")
api.add_resource(SubmissionStatusResource, "/<int:submission_id>/status")
