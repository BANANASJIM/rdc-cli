"""Tests for Phase 5B mock capture types."""

from __future__ import annotations

import mock_renderdoc as rd


class TestCaptureOptions:
    def test_capture_options_defaults(self) -> None:
        """SWIG zero-initializes all fields; real defaults come from GetDefaultCaptureOptions()."""
        opts = rd.CaptureOptions()
        assert opts.allowFullscreen is False
        assert opts.allowVSync is False
        assert opts.apiValidation is False
        assert opts.captureCallstacks is False
        assert opts.captureCallstacksOnlyActions is False
        assert opts.delayForDebugger == 0
        assert opts.verifyBufferAccess is False
        assert opts.hookIntoChildren is False
        assert opts.refAllResources is False
        assert opts.captureAllCmdLists is False
        assert opts.debugOutputMute is False
        assert opts.softMemoryLimit == 0

    def test_capture_options_writable(self) -> None:
        opts = rd.CaptureOptions()
        opts.allowFullscreen = True
        opts.allowVSync = True
        opts.apiValidation = True
        opts.captureCallstacks = True
        opts.captureCallstacksOnlyActions = True
        opts.delayForDebugger = 5
        opts.verifyBufferAccess = True
        opts.hookIntoChildren = True
        opts.refAllResources = True
        opts.captureAllCmdLists = True
        opts.debugOutputMute = True
        opts.softMemoryLimit = 1024

        assert opts.allowFullscreen is True
        assert opts.allowVSync is True
        assert opts.apiValidation is True
        assert opts.captureCallstacks is True
        assert opts.captureCallstacksOnlyActions is True
        assert opts.delayForDebugger == 5
        assert opts.verifyBufferAccess is True
        assert opts.hookIntoChildren is True
        assert opts.refAllResources is True
        assert opts.captureAllCmdLists is True
        assert opts.debugOutputMute is True
        assert opts.softMemoryLimit == 1024


class TestExecuteResult:
    def test_execute_result_fields(self) -> None:
        er = rd.ExecuteResult(result=0, ident=1234)
        assert er.result == 0
        assert er.ident == 1234


class TestTargetControlMessageType:
    def test_target_control_message_type_values(self) -> None:
        tcmt = rd.TargetControlMessageType
        assert tcmt.Unknown == 0
        assert tcmt.Disconnected == 1
        assert tcmt.Busy == 2
        assert tcmt.Noop == 3
        assert tcmt.NewCapture == 4
        assert tcmt.CaptureCopied == 5
        assert tcmt.RegisterAPI == 6
        assert tcmt.NewChild == 7
        assert tcmt.CaptureProgress == 8
        assert tcmt.CapturableWindowCount == 9
        assert tcmt.RequestShow == 10
        assert len(tcmt) == 11


class TestNewCaptureData:
    def test_new_capture_data_fields(self) -> None:
        ncd = rd.NewCaptureData()
        assert ncd.captureId == 0
        assert ncd.frameNumber == 0
        assert ncd.path == ""
        assert ncd.byteSize == 0
        assert ncd.timestamp == 0
        assert ncd.thumbnail == b""
        assert ncd.thumbWidth == 0
        assert ncd.thumbHeight == 0
        assert ncd.title == ""
        assert ncd.api == ""
        assert ncd.local is True


class TestThumbnail:
    def test_thumbnail_data_fields(self) -> None:
        td = rd.Thumbnail(data=b"abc", width=16, height=16)
        assert td.data == b"abc"
        assert td.width == 16
        assert td.height == 16


class TestGPUDevice:
    def test_gpu_device_fields(self) -> None:
        gpu = rd.GPUDevice()
        assert gpu.name == ""
        assert isinstance(gpu.vendor, int)
        assert isinstance(gpu.deviceID, int)
        assert isinstance(gpu.driver, str)


class TestSectionProperties:
    def test_section_properties_fields(self) -> None:
        sp = rd.SectionProperties()
        assert sp.name == ""
        assert sp.type == rd.SectionType.Unknown
        assert sp.version == ""
        assert sp.compressedSize == 0
        assert sp.uncompressedSize == 0
        assert sp.flags == rd.SectionFlags.NoFlags


class TestSectionType:
    def test_section_type_values(self) -> None:
        st = rd.SectionType
        assert st.Unknown == 0
        assert st.FrameCapture == 1
        assert st.ResolveDatabase == 2
        assert st.Bookmarks == 3
        assert st.Notes == 4
        assert st.ResourceRenames == 5
        assert st.AMDRGPProfile == 6
        assert st.ExtendedThumbnail == 7


class TestSectionFlags:
    def test_section_flags_values(self) -> None:
        sf = rd.SectionFlags
        assert sf.NoFlags == 0
        assert sf.ASCIIStored == 1
        assert sf.LZ4Compressed == 2
        assert sf.ZstdCompressed == 4
        combined = sf.ZstdCompressed | sf.ASCIIStored
        assert combined == 5


class TestMockTargetControl:
    def test_mock_target_control_connected(self) -> None:
        tc = rd.MockTargetControl()
        assert tc.Connected() is True

    def test_mock_target_control_receive_message(self) -> None:
        tc = rd.MockTargetControl()
        msg = tc.ReceiveMessage(progress=None)
        assert isinstance(msg, rd.TargetControlMessage)
        assert msg.type == rd.TargetControlMessageType.Noop

    def test_mock_target_control_trigger_capture(self) -> None:
        tc = rd.MockTargetControl()
        tc.TriggerCapture(1)

    def test_mock_target_control_queue_capture(self) -> None:
        tc = rd.MockTargetControl()
        tc.QueueCapture(0, 1)

    def test_mock_target_control_copy_capture(self) -> None:
        tc = rd.MockTargetControl()
        tc.CopyCapture(0, "/tmp/x.rdc")

    def test_mock_target_control_shutdown(self) -> None:
        tc = rd.MockTargetControl()
        tc.Shutdown()
        assert tc.Connected() is False

    def test_mock_target_control_get_target(self) -> None:
        tc = rd.MockTargetControl()
        assert isinstance(tc.GetTarget(), str)

    def test_mock_target_control_get_pid(self) -> None:
        tc = rd.MockTargetControl()
        assert isinstance(tc.GetPID(), int)

    def test_mock_target_control_get_api(self) -> None:
        tc = rd.MockTargetControl()
        assert isinstance(tc.GetAPI(), str)


class TestMockCaptureFileExtensions:
    def test_mock_capturefile_get_thumbnail(self) -> None:
        cf = rd.MockCaptureFile()
        thumb = cf.GetThumbnail(0, 256)
        assert isinstance(thumb, rd.Thumbnail)
        assert isinstance(thumb.data, bytes)
        assert len(thumb.data) > 0

    def test_mock_capturefile_get_available_gpus(self) -> None:
        cf = rd.MockCaptureFile()
        gpus = cf.GetAvailableGPUs()
        assert isinstance(gpus, list)
        assert len(gpus) > 0
        assert isinstance(gpus[0], rd.GPUDevice)

    def test_mock_capturefile_get_section_count(self) -> None:
        cf = rd.MockCaptureFile()
        count = cf.GetSectionCount()
        assert isinstance(count, int)
        assert count >= 0

    def test_mock_capturefile_get_section_properties(self) -> None:
        cf = rd.MockCaptureFile()
        props = cf.GetSectionProperties(0)
        assert isinstance(props, rd.SectionProperties)

    def test_mock_capturefile_get_section_contents(self) -> None:
        cf = rd.MockCaptureFile()
        data = cf.GetSectionContents(0)
        assert isinstance(data, bytes)

    def test_mock_capturefile_find_section_by_name(self) -> None:
        cf = rd.MockCaptureFile()
        assert cf.FindSectionByName("FrameCapture") == 0
        assert cf.FindSectionByName("missing") == -1

    def test_mock_capturefile_has_callstacks(self) -> None:
        cf = rd.MockCaptureFile()
        assert isinstance(cf.HasCallstacks(), bool)

    def test_mock_capturefile_recorded_machine_ident(self) -> None:
        cf = rd.MockCaptureFile()
        assert isinstance(cf.RecordedMachineIdent(), str)

    def test_mock_capturefile_timestamp_base(self) -> None:
        cf = rd.MockCaptureFile()
        assert isinstance(cf.TimestampBase(), int)

    def test_mock_capturefile_has_pending_dependencies(self) -> None:
        cf = rd.MockCaptureFile()
        assert isinstance(cf.HasPendingDependencies(), bool)

    def test_mock_capturefile_embed_dependencies(self) -> None:
        cf = rd.MockCaptureFile()
        cf.EmbedDependenciesIntoCapture()


class TestModuleLevelFunctions:
    def test_execute_and_inject(self) -> None:
        result = rd.ExecuteAndInject(
            "app", "/tmp", "", [], "/tmp/cap.rdc", rd.CaptureOptions(), False
        )
        assert isinstance(result, rd.ExecuteResult)

    def test_create_target_control(self) -> None:
        tc = rd.CreateTargetControl("", 12345, "rdc-cli", True)
        assert isinstance(tc, rd.MockTargetControl)

    def test_get_default_capture_options(self) -> None:
        opts = rd.GetDefaultCaptureOptions()
        assert isinstance(opts, rd.CaptureOptions)
        assert opts.allowFullscreen is True
        assert opts.allowVSync is True
        assert opts.debugOutputMute is True
