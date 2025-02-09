# SPDX-License-Identifier: MIT
# Copyright (c) 2025 Matthias Bilger <matthias@bilger.info>
from enum import Enum
from typing import ClassVar
from typing import Optional

from pydantic import BaseModel
from pydantic import Field


class MeetingPermissions(BaseModel):
    """Permissions for the meeting communicated by teams."""

    can_toggle_mute: bool = Field(False, alias="canToggleMute")
    can_toggle_video: bool = Field(False, alias="canToggleVideo")
    can_toggle_hand: bool = Field(False, alias="canToggleHand")
    can_toggle_blur: bool = Field(False, alias="canToggleBlur")
    can_leave: bool = Field(False, alias="canLeave")
    can_react: bool = Field(False, alias="canReact")
    can_toggle_share_tray: bool = Field(False, alias="canToggleShareTray")
    can_toggle_chat: bool = Field(False, alias="canToggleChat")
    can_stop_sharing: bool = Field(False, alias="canStopSharing")
    can_pair: bool = Field(False, alias="canPair")


class MeetingState(BaseModel):
    """Current state of the meeting communicated by teams."""

    is_muted: bool = Field(False, alias="isMuted")
    is_hand_raised: bool = Field(False, alias="isHandRaised")
    is_in_meeting: bool = Field(False, alias="isInMeeting")
    is_recording_on: bool = Field(False, alias="isRecordingOn")
    is_background_blurred: bool = Field(False, alias="isBackgroundBlurred")
    is_sharing: bool = Field(False, alias="isSharing")
    has_unread_messages: bool = Field(False, alias="hasUnreadMessages")
    is_video_on: bool = Field(False, alias="isVideoOn")


class MeetingUpdate(BaseModel):
    """Update of the meeting state communicated by teams."""

    meeting_permissions: Optional[MeetingPermissions] = Field(
        None,
        alias="meetingPermissions",
    )
    meeting_state: Optional[MeetingState] = Field(None, alias="meetingState")


class ServerMessage(BaseModel):
    """Message received from the Teams WebSocket server."""

    request_id: Optional[int] = Field(None, alias="requestId")
    response: Optional[str] = None
    error_msg: Optional[str] = Field(None, alias="errorMsg")
    token_refresh: Optional[str] = Field(None, alias="tokenRefresh")
    meeting_update: Optional[MeetingUpdate] = Field(None, alias="meetingUpdate")


class ClientMessageParameterType(str, Enum):
    """Types of reactions for client messages."""

    ReactApplause = "applause"
    ReactLaugh = "laugh"
    ReactLike = "like"
    ReactLove = "love"
    ReactWow = "wow"
    ToggleUiChat = "chat"
    ToggleUiSharing = "sharing-tray"


class ClientMessageParameter(BaseModel):
    type_: ClientMessageParameterType = Field(..., serialization_alias="type")


class MeetingAction(str, Enum):
    NoneAction = "none"
    QueryMeetingState = "query-state"
    Mute = "mute"
    Unmute = "unmute"
    ToggleMute = "toggle-mute"
    HideVideo = "hide-video"
    ShowVideo = "show-video"
    ToggleVideo = "toggle-video"
    UnblurBackground = "unblur-background"
    BlurBackground = "blur-background"
    ToggleBlurBackground = "toggle-background-blur"
    LowerHand = "lower-hand"
    RaiseHand = "raise-hand"
    ToggleHand = "toggle-hand"
    LeaveCall = "leave-call"
    React = "send-reaction"
    ToggleUI = "toggle-ui"
    StopSharing = "stop-sharing"


class ClientMessage(BaseModel):
    """Message sent to the Teams WebSocket server."""

    action: MeetingAction
    parameters: Optional[ClientMessageParameter] = None
    request_id: int = Field(None, serialization_alias="requestId")

    _request_id_counter: ClassVar[int] = 0
    """Each message must have a unique request_id. The counter is incremented for each message automatically."""

    @classmethod
    def create(cls, *args, **kwargs) -> "ClientMessage":
        cls._request_id_counter += 1
        kwargs["request_id"] = cls._request_id_counter
        return cls(*args, **kwargs)
