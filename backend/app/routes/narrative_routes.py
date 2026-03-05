# pyright: reportMissingImports=false
from flask import Blueprint, request, jsonify
from app.services.narrative_analyzer import narrative_analyzer, legacy_narrative_analyzer
import logging

narrative_bp = Blueprint('narrative', __name__)
logger = logging.getLogger(__name__)

@narrative_bp.route('/analyze-narrative', methods=['POST'])
def analyze_narrative():
    """
    Analyze narrative structure of video segments
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
        
        segments = data.get('segments', [])
        video_duration = data.get('video_duration')
        enable_ai_override = data.get('enable_ai_override', True)
        user_override_segments = data.get('user_override_segments', [])
        scene_type_priority = data.get('scene_type_priority', {})
        
        if not segments:
            return jsonify({"error": "No segments provided"}), 400
        
        logger.info(f"Analyzing narrative structure for {len(segments)} segments")
        
        # Configure AI override settings
        if enable_ai_override:
            legacy_narrative_analyzer.enable_ai_override()
        else:
            legacy_narrative_analyzer.disable_ai_override()
        
        # Add user override segments if provided
        if user_override_segments:
            for segment in user_override_segments:
                legacy_narrative_analyzer.add_user_override_segment(segment)
        
        # Update scene type priority if provided
        if scene_type_priority:
            legacy_narrative_analyzer.scene_type_priority.update(scene_type_priority)
        
        # Perform narrative analysis
        analysis_result = legacy_narrative_analyzer.analyze_narrative_structure(
            segments=segments,
            video_duration=video_duration
        )
        
        if "error" in analysis_result:
            return jsonify(analysis_result), 400
        
        # Apply user overrides if enabled
        if enable_ai_override and user_override_segments:
            analysis_result["narrative_segments"] = legacy_narrative_analyzer.apply_user_overrides(
                analysis_result["narrative_segments"]
            )
        
        # Get AI suggestions if enabled
        ai_suggestions = []
        if enable_ai_override:
            ai_suggestions = legacy_narrative_analyzer.get_ai_suggestions(segments)
        
        # Prepare response
        response_data = {
            "narrative_segments": analysis_result.get("narrative_segments", []),
            "concatenation_plan": analysis_result.get("concatenation_plan", {}),
            "narrative_flow": analysis_result.get("narrative_flow", ""),
            "total_segments": analysis_result.get("total_segments", 0),
            "estimated_final_duration": analysis_result.get("estimated_final_duration", 0),
            "ai_suggestions": ai_suggestions,
            "scene_type_priority": legacy_narrative_analyzer.scene_type_priority,
            "user_override_segments": user_override_segments,
            "ai_override_enabled": enable_ai_override
        }
        
        logger.info(f"Narrative analysis completed successfully. Found {len(analysis_result.get('narrative_segments', []))} narrative segments")
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Error in narrative analysis: {str(e)}")
        return jsonify({"error": f"Narrative analysis failed: {str(e)}"}), 500

@narrative_bp.route('/narrative-elements', methods=['GET'])
def get_narrative_elements():
    """
    Get available narrative element types and their descriptions
    """
    try:
        elements = {
            "opening": {
                "name": "Opening",
                "description": "Introduction and setup of the story",
                "icon": "🎬",
                "typical_position": "Beginning (0-15%)"
            },
            "hook": {
                "name": "Hook",
                "description": "Attention-grabbing moment that draws viewers in",
                "icon": "🎣",
                "typical_position": "Early (5-25%)"
            },
            "rising_action": {
                "name": "Rising Action",
                "description": "Building tension and developing the story",
                "icon": "📈",
                "typical_position": "Middle (20-70%)"
            },
            "emotional_moment": {
                "name": "Emotional Moment",
                "description": "High emotional impact scenes",
                "icon": "💝",
                "typical_position": "Throughout"
            },
            "action_sequence": {
                "name": "Action Sequence",
                "description": "High-energy, fast-paced moments",
                "icon": "⚡",
                "typical_position": "Throughout"
            },
            "climax": {
                "name": "Climax",
                "description": "Peak moment of tension or revelation",
                "icon": "🎯",
                "typical_position": "Late (60-90%)"
            },
            "conclusion": {
                "name": "Conclusion",
                "description": "Resolution and wrap-up",
                "icon": "🏁",
                "typical_position": "End (85-100%)"
            }
        }
        
        return jsonify({"elements": elements}), 200
        
    except Exception as e:
        logger.error(f"Error getting narrative elements: {str(e)}")
        return jsonify({"error": "Failed to get narrative elements"}), 500
