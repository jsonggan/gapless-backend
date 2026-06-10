"""Learning path endpoints."""

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import CurrentActiveUserDep, DBDep
from app.crud.learning_path import learning_path as learning_path_crud
from app.schemas.learning_path import (
    LearningPathDetail,
    LearningPathModuleProgressResult,
    LearningPathModuleProgressUpdate,
    LearningPathSummary,
    LearningPathTitle,
)

router = APIRouter()


@router.get("/titles", response_model=list[LearningPathTitle])
async def list_learning_path_titles(
    db: DBDep,
    current_user: CurrentActiveUserDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[LearningPathTitle]:
    """List lightweight learning path title metadata for frontend selectors."""
    paths = await learning_path_crud.list_for_user(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    progress_rows = await learning_path_crud.progress_for_paths(
        db,
        user_id=current_user.id,
        paths=paths,
    )
    return [learning_path_crud.to_title(path, progress_rows) for path in paths]


@router.get("/", response_model=list[LearningPathSummary])
async def list_learning_paths(
    db: DBDep,
    current_user: CurrentActiveUserDep,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[LearningPathSummary]:
    """List the current user's learning paths with progress summary."""
    paths = await learning_path_crud.list_for_user(
        db,
        user_id=current_user.id,
        skip=skip,
        limit=limit,
    )
    progress_rows = await learning_path_crud.progress_for_paths(
        db,
        user_id=current_user.id,
        paths=paths,
    )
    return [learning_path_crud.to_summary(path, progress_rows) for path in paths]


@router.get("/{learning_path_id}", response_model=LearningPathDetail)
async def get_learning_path(
    db: DBDep,
    current_user: CurrentActiveUserDep,
    learning_path_id: int,
) -> LearningPathDetail:
    """Get a full learning path with modules and current read state."""
    path = await learning_path_crud.get_for_user(
        db,
        user_id=current_user.id,
        learning_path_id=learning_path_id,
    )
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Learning path not found")

    progress_rows = await learning_path_crud.progress_for_paths(
        db,
        user_id=current_user.id,
        paths=[path],
    )
    return learning_path_crud.to_detail(path, progress_rows)


@router.patch(
    "/{learning_path_id}/modules/{module_id}/progress",
    response_model=LearningPathModuleProgressResult,
)
async def set_module_progress(
    db: DBDep,
    current_user: CurrentActiveUserDep,
    learning_path_id: int,
    module_id: int,
    request: LearningPathModuleProgressUpdate,
) -> LearningPathModuleProgressResult:
    """Set whether a module has been read by the current user."""
    result = await learning_path_crud.set_module_read(
        db,
        user_id=current_user.id,
        learning_path_id=learning_path_id,
        module_id=module_id,
        is_read=request.is_read,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Learning module not found"
        )
    return result


@router.post(
    "/{learning_path_id}/modules/{module_id}/read",
    response_model=LearningPathModuleProgressResult,
)
async def mark_module_read(
    db: DBDep,
    current_user: CurrentActiveUserDep,
    learning_path_id: int,
    module_id: int,
) -> LearningPathModuleProgressResult:
    """Mark a module as read."""
    result = await learning_path_crud.set_module_read(
        db,
        user_id=current_user.id,
        learning_path_id=learning_path_id,
        module_id=module_id,
        is_read=True,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Learning module not found"
        )
    return result


@router.delete(
    "/{learning_path_id}/modules/{module_id}/read",
    response_model=LearningPathModuleProgressResult,
)
async def mark_module_unread(
    db: DBDep,
    current_user: CurrentActiveUserDep,
    learning_path_id: int,
    module_id: int,
) -> LearningPathModuleProgressResult:
    """Mark a module as unread."""
    result = await learning_path_crud.set_module_read(
        db,
        user_id=current_user.id,
        learning_path_id=learning_path_id,
        module_id=module_id,
        is_read=False,
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Learning module not found"
        )
    return result
